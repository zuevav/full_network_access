from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json
import httpx
import re
from urllib.parse import urlparse
from typing import Set

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, ClientDomain, DomainTemplate
from app.schemas.domain import (
    DomainCreate, DomainResponse, ApplyTemplateRequest,
    DomainAnalyzeRequest, DomainAnalyzeResponse
)
from app.utils.helpers import normalize_domain


router = APIRouter()


def extract_domain_from_url(url: str) -> str | None:
    """Extract domain from URL."""
    try:
        if not url.startswith(('http://', 'https://', '//')):
            if url.startswith('/'):
                return None  # Relative path
            url = 'https://' + url
        elif url.startswith('//'):
            url = 'https:' + url
        parsed = urlparse(url)
        if parsed.netloc:
            # Remove port if present
            domain = parsed.netloc.split(':')[0]
            # Skip IP addresses
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
                return None
            return domain.lower()
    except Exception:
        pass
    return None


def get_base_domain(domain: str) -> str:
    """Get base domain (remove www prefix)."""
    if domain.startswith('www.'):
        return domain[4:]
    return domain


async def analyze_domain_resources(domain: str) -> tuple[Set[str], Set[str], str | None]:
    """
    Analyze a domain for redirects and external resources.
    Returns: (redirect_domains, resource_domains, error)
    """
    redirect_domains: Set[str] = set()
    resource_domains: Set[str] = set()
    error = None

    # Normalize domain
    normalized = normalize_domain(domain)
    if not normalized:
        return redirect_domains, resource_domains, "Invalid domain"

    base_domain = get_base_domain(normalized)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            verify=False,  # Allow self-signed certs
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        ) as client:
            # Try HTTPS first, then HTTP
            for protocol in ['https', 'http']:
                try:
                    url = f"{protocol}://{normalized}"
                    response = await client.get(url)

                    # Collect redirect chain domains
                    for hist in response.history:
                        redirect_domain = extract_domain_from_url(str(hist.url))
                        if redirect_domain and get_base_domain(redirect_domain) != base_domain:
                            redirect_domains.add(redirect_domain)

                    # Check final URL domain
                    final_domain = extract_domain_from_url(str(response.url))
                    if final_domain and get_base_domain(final_domain) != base_domain:
                        redirect_domains.add(final_domain)

                    # Parse HTML for external resources
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' in content_type:
                        html = response.text

                        # Find all URLs in src, href, srcset attributes
                        patterns = [
                            r'(?:src|href)\s*=\s*["\']([^"\']+)["\']',
                            r'url\(["\']?([^"\')\s]+)["\']?\)',
                            r'srcset\s*=\s*["\']([^"\']+)["\']',
                        ]

                        found_urls = set()
                        for pattern in patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            found_urls.update(matches)

                        # Handle srcset (comma-separated URLs with sizes)
                        for url_str in list(found_urls):
                            if ',' in url_str and ' ' in url_str:
                                # Likely a srcset value
                                for part in url_str.split(','):
                                    url_part = part.strip().split()[0] if part.strip() else ''
                                    if url_part:
                                        found_urls.add(url_part)

                        # Extract domains from URLs
                        for found_url in found_urls:
                            res_domain = extract_domain_from_url(found_url)
                            if res_domain and get_base_domain(res_domain) != base_domain:
                                resource_domains.add(res_domain)

                    break  # Success, don't try HTTP

                except httpx.HTTPStatusError:
                    continue
                except Exception:
                    continue

    except httpx.TimeoutException:
        error = "Connection timeout"
    except httpx.ConnectError:
        error = "Connection failed"
    except Exception as e:
        error = str(e)[:100]

    return redirect_domains, resource_domains, error


@router.post("/analyze", response_model=DomainAnalyzeResponse)
async def analyze_domain(
    request: DomainAnalyzeRequest,
    admin: CurrentAdmin
):
    """
    Analyze a domain to find related domains (redirects, CDNs, APIs).
    Returns suggestions for additional domains to add.
    """
    original = normalize_domain(request.domain)
    if not original:
        raise HTTPException(status_code=400, detail="Invalid domain")

    redirect_domains, resource_domains, error = await analyze_domain_resources(request.domain)

    # Combine all suggestions, removing duplicates
    all_suggested = redirect_domains | resource_domains

    # Filter out common CDN/tracking domains that are usually not needed
    common_skip = {
        'google-analytics.com', 'googletagmanager.com', 'doubleclick.net',
        'facebook.net', 'fbcdn.net', 'twitter.com', 'twimg.com',
        'addthis.com', 'sharethis.com', 'disqus.com'
    }

    suggested = sorted([d for d in all_suggested if get_base_domain(d) not in common_skip])

    return DomainAnalyzeResponse(
        original_domain=original,
        redirects=sorted(redirect_domains),
        resources=sorted(resource_domains - redirect_domains),  # Exclude redirects from resources
        suggested=suggested,
        error=error
    )


@router.get("/{client_id}/domains", response_model=list[DomainResponse])
async def list_client_domains(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """List all domains for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return [
        DomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in client.domains
    ]


@router.post("/{client_id}/domains", response_model=list[DomainResponse], status_code=status.HTTP_201_CREATED)
async def add_client_domains(
    client_id: int,
    request: DomainCreate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Add domains to a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get existing domains
    result = await db.execute(
        select(ClientDomain).where(ClientDomain.client_id == client_id)
    )
    existing_domains = {d.domain for d in result.scalars().all()}

    added_domains = []
    for domain in request.domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in existing_domains:
            client_domain = ClientDomain(
                client_id=client_id,
                domain=normalized,
                include_subdomains=request.include_subdomains,
                is_active=True
            )
            db.add(client_domain)
            added_domains.append(client_domain)
            existing_domains.add(normalized)

    await db.commit()

    return [
        DomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in added_domains
    ]


@router.delete("/{client_id}/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_domain(
    client_id: int,
    domain_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Delete a domain from a client."""
    result = await db.execute(
        select(ClientDomain)
        .where(ClientDomain.id == domain_id, ClientDomain.client_id == client_id)
    )
    domain = result.scalar_one_or_none()

    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.delete(domain)
    await db.commit()


@router.post("/{client_id}/domains/template", response_model=list[DomainResponse])
async def apply_template(
    client_id: int,
    request: ApplyTemplateRequest,
    db: DBSession,
    admin: CurrentAdmin
):
    """Apply a domain template to a client."""
    # Check client exists
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get template
    result = await db.execute(
        select(DomainTemplate).where(DomainTemplate.id == request.template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    # Parse template domains
    template_domains = json.loads(template.domains_json)

    # Get existing domains
    result = await db.execute(
        select(ClientDomain).where(ClientDomain.client_id == client_id)
    )
    existing_domains = {d.domain for d in result.scalars().all()}

    added_domains = []
    for domain in template_domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in existing_domains:
            client_domain = ClientDomain(
                client_id=client_id,
                domain=normalized,
                include_subdomains=True,
                is_active=True
            )
            db.add(client_domain)
            added_domains.append(client_domain)
            existing_domains.add(normalized)

    await db.commit()

    return [
        DomainResponse(
            id=d.id,
            domain=d.domain,
            include_subdomains=d.include_subdomains,
            is_active=d.is_active,
            added_at=d.added_at
        )
        for d in added_domains
    ]


@router.post("/{client_id}/domains/sync", status_code=status.HTTP_200_OK)
async def sync_domains(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Sync/resolve domains to IP routes for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains), selectinload(Client.vpn_config))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # TODO: Implement domain resolver integration
    # For now, return success
    return {"message": "Domain routes synced", "domains_count": len(client.domains)}
