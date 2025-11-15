#!/usr/bin/env python3
"""
測試執行腳本
支援不同的測試模式和選項
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """執行命令並顯示結果"""
    print(f"\n🚀 {description}")
    print(f"執行命令: {' '.join(command)}")
    print("-" * 60)
    
    result = subprocess.run(command, capture_output=False)
    
    if result.returncode == 0:
        print(f" {description} 成功完成")
    else:
        print(f" {description} 失敗 (退出碼: {result.returncode})")
        return False
    return True

def main():
    """主執行函數"""
    print("🧪 Form Analysis Backend - 測試執行器")
    print("=" * 60)
    
    # 確保在正確的目錄
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python run_tests.py [模式] [選項...]")
        print("")
        print("模式:")
        print("  all       - 執行所有測試")
        print("  unit      - 僅執行單元測試")
        print("  integration - 僅執行整合測試")
        print("  models    - 僅執行模型測試")
        print("  coverage  - 執行測試並生成覆蓋率報告")
        print("  fast      - 快速測試（跳過慢速測試）")
        print("")
        print("範例:")
        print("  python run_tests.py all")
        print("  python run_tests.py models")
        print("  python run_tests.py coverage")
        print("  python run_tests.py fast -v")
        return 1
    
    mode = sys.argv[1].lower()
    extra_args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # 基礎 pytest 命令
    base_cmd = ["python", "-m", "pytest"]
    
    # 根據模式設置參數
    if mode == "all":
        cmd = base_cmd + ["tests/"] + extra_args
        description = "執行所有測試"
        
    elif mode == "unit":
        cmd = base_cmd + ["-m", "unit", "tests/"] + extra_args
        description = "執行單元測試"
        
    elif mode == "integration":
        cmd = base_cmd + ["-m", "integration", "tests/"] + extra_args
        description = "執行整合測試"
        
    elif mode == "models":
        cmd = base_cmd + [
            "tests/test_upload_job.py",
            "tests/test_record.py", 
            "tests/test_upload_error.py",
            "tests/test_integration.py"
        ] + extra_args
        description = "執行模型測試"
        
    elif mode == "coverage":
        cmd = base_cmd + [
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "--cov-fail-under=70",
            "tests/"
        ] + extra_args
        description = "執行測試並生成覆蓋率報告"
        
    elif mode == "fast":
        cmd = base_cmd + ["-m", "not slow", "tests/"] + extra_args
        description = "執行快速測試"
        
    else:
        print(f" 未知模式: {mode}")
        return 1
    
    # 執行測試
    success = run_command(cmd, description)
    
    if success:
        print(f"\n🎉 測試執行完成!")
        if mode == "coverage":
            print(f" 覆蓋率報告已生成:")
            print(f"   - HTML 報告: htmlcov/index.html")
            print(f"   - XML 報告: coverage.xml")
    else:
        print(f"\n💥 測試執行失敗!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())