import { useTranslation } from 'react-i18next'

export function InitPage() {
  const { t } = useTranslation()

  return (
    <div className="register-page">
      <section className="register-card">
        <h2 className="register-title">{t('init.title')}</h2>
        <p className="register-hint">{t('init.disabledHint')}</p>
      </section>
    </div>
  )
}
