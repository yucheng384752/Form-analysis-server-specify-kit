import { useTranslation } from 'react-i18next';

const APP_VERSION = '1.0.0';

export function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-border/40 bg-background/95">
      <div className="container flex h-14 max-w-screen-2xl items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {t('footer.copyright')}
        </div>
        <div className="flex items-center space-x-4 text-sm text-muted-foreground">
          <span>{t('footer.version', { version: APP_VERSION })}</span>
        </div>
      </div>
    </footer>
  );
}