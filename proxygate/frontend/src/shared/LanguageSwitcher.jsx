import { useTranslation } from 'react-i18next'
import { Globe } from 'lucide-react'

const languages = [
  { code: 'en', name: 'English', flag: 'EN' },
  { code: 'ru', name: 'Русский', flag: 'RU' }
]

export default function LanguageSwitcher({ className = '' }) {
  const { i18n } = useTranslation()

  const currentLang = languages.find(l => l.code === i18n.language) || languages[0]

  const handleChange = (langCode) => {
    i18n.changeLanguage(langCode)
  }

  return (
    <div className={`relative group ${className}`}>
      <button className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors">
        <Globe className="w-4 h-4" />
        <span className="text-sm font-medium">{currentLang.flag}</span>
      </button>

      <div className="absolute right-0 mt-1 py-1 bg-white rounded-lg shadow-lg border border-gray-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 min-w-[120px]">
        {languages.map((lang) => (
          <button
            key={lang.code}
            onClick={() => handleChange(lang.code)}
            className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
              i18n.language === lang.code ? 'text-primary-600 font-medium' : 'text-gray-700'
            }`}
          >
            {lang.name}
          </button>
        ))}
      </div>
    </div>
  )
}
