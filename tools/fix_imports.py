#!/usr/bin/env python3
"""
修復 UI 組件中帶版本號的導入語句
"""

import os
import re
import glob

def fix_imports_in_file(file_path):
    """修復單個文件中的導入語句"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 修復常見的帶版本號的導入
        patterns = [
            (r'@radix-ui/react-slot@[\d\.]+', '@radix-ui/react-slot'),
            (r'class-variance-authority@[\d\.]+', 'class-variance-authority'),
            (r'lucide-react@[\d\.]+', 'lucide-react'),
            (r'@radix-ui/react-accordion@[\d\.]+', '@radix-ui/react-accordion'),
            (r'@radix-ui/react-alert-dialog@[\d\.]+', '@radix-ui/react-alert-dialog'),
            (r'@radix-ui/react-aspect-ratio@[\d\.]+', '@radix-ui/react-aspect-ratio'),
            (r'@radix-ui/react-avatar@[\d\.]+', '@radix-ui/react-avatar'),
            (r'@radix-ui/react-checkbox@[\d\.]+', '@radix-ui/react-checkbox'),
            (r'@radix-ui/react-collapsible@[\d\.]+', '@radix-ui/react-collapsible'),
            (r'@radix-ui/react-context-menu@[\d\.]+', '@radix-ui/react-context-menu'),
            (r'@radix-ui/react-dialog@[\d\.]+', '@radix-ui/react-dialog'),
            (r'@radix-ui/react-dropdown-menu@[\d\.]+', '@radix-ui/react-dropdown-menu'),
            (r'@radix-ui/react-hover-card@[\d\.]+', '@radix-ui/react-hover-card'),
            (r'@radix-ui/react-label@[\d\.]+', '@radix-ui/react-label'),
            (r'@radix-ui/react-menubar@[\d\.]+', '@radix-ui/react-menubar'),
            (r'@radix-ui/react-navigation-menu@[\d\.]+', '@radix-ui/react-navigation-menu'),
            (r'@radix-ui/react-popover@[\d\.]+', '@radix-ui/react-popover'),
            (r'@radix-ui/react-progress@[\d\.]+', '@radix-ui/react-progress'),
            (r'@radix-ui/react-radio-group@[\d\.]+', '@radix-ui/react-radio-group'),
            (r'@radix-ui/react-scroll-area@[\d\.]+', '@radix-ui/react-scroll-area'),
            (r'@radix-ui/react-select@[\d\.]+', '@radix-ui/react-select'),
            (r'@radix-ui/react-separator@[\d\.]+', '@radix-ui/react-separator'),
            (r'@radix-ui/react-slider@[\d\.]+', '@radix-ui/react-slider'),
            (r'@radix-ui/react-switch@[\d\.]+', '@radix-ui/react-switch'),
            (r'@radix-ui/react-tabs@[\d\.]+', '@radix-ui/react-tabs'),
            (r'@radix-ui/react-toggle@[\d\.]+', '@radix-ui/react-toggle'),
            (r'@radix-ui/react-toggle-group@[\d\.]+', '@radix-ui/react-toggle-group'),
            (r'@radix-ui/react-tooltip@[\d\.]+', '@radix-ui/react-tooltip'),
            (r'next-themes@[\d\.]+', 'next-themes'),
            (r'sonner@[\d\.]+', 'sonner'),
            (r'cmdk@[\d\.]+', 'cmdk'),
            (r'vaul@[\d\.]+', 'vaul'),
            (r'input-otp@[\d\.]+', 'input-otp'),
            (r'react-day-picker@[\d\.]+', 'react-day-picker'),
            (r'embla-carousel-react@[\d\.]+', 'embla-carousel-react'),
            (r'recharts@[\d\.]+', 'recharts'),
            (r'react-resizable-panels@[\d\.]+', 'react-resizable-panels'),
            (r'react-hook-form@[\d\.]+', 'react-hook-form'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # 如果內容有變化，寫回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"已修復: {file_path}")
            return True
        else:
            print(f"無需修復: {file_path}")
            return False
            
    except Exception as e:
        print(f"修復 {file_path} 時發生錯誤: {e}")
        return False

def main():
    # 找到所有 .tsx 和 .ts 文件
    base_dir = r"C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\frontend\src"
    
    if not os.path.exists(base_dir):
        print(f"目錄不存在: {base_dir}")
        return
    
    # 搜尋所有 TypeScript 文件
    tsx_files = glob.glob(os.path.join(base_dir, "**", "*.tsx"), recursive=True)
    ts_files = glob.glob(os.path.join(base_dir, "**", "*.ts"), recursive=True)
    
    all_files = tsx_files + ts_files
    
    print(f"找到 {len(all_files)} 個文件")
    
    fixed_count = 0
    for file_path in all_files:
        if fix_imports_in_file(file_path):
            fixed_count += 1
    
    print(f"總共修復了 {fixed_count} 個文件")

if __name__ == "__main__":
    main()