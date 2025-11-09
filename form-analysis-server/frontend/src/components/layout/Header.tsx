import { ReactNode } from 'react';

interface HeaderProps {
  children?: ReactNode;
}

export function Header({ children }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        <div className="mr-4 flex">
          <a className="mr-6 flex items-center space-x-2" href="/">
            <span className="hidden font-bold sm:inline-block">
              表單分析系統
            </span>
          </a>
          <nav className="flex items-center gap-6 text-sm">
            <a
              className="transition-colors hover:text-foreground/80 text-foreground/60"
              href="/"
            >
              首頁
            </a>
            <a
              className="transition-colors hover:text-foreground/80 text-foreground/60"
              href="/upload"
            >
              上傳檔案
            </a>
            <a
              className="transition-colors hover:text-foreground/80 text-foreground/60"
              href="/view"
            >
              查詢資料
            </a>
          </nav>
        </div>
        <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
          {children}
        </div>
      </div>
    </header>
  );
}