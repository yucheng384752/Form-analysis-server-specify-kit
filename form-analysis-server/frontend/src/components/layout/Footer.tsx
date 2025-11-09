export function Footer() {
  return (
    <footer className="border-t border-border/40 bg-background/95">
      <div className="container flex h-14 max-w-screen-2xl items-center justify-between">
        <div className="text-sm text-muted-foreground">
          © 2024 表單分析系統. All rights reserved.
        </div>
        <div className="flex items-center space-x-4 text-sm text-muted-foreground">
          <span>版本 1.0.0</span>
        </div>
      </div>
    </footer>
  );
}