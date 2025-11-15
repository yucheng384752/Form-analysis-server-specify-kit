"""
配置一致性檢查工具
檢查 config.py、docker-compose.yml、.env.example 之間的配置一致性
"""
import re
import yaml
from pathlib import Path
from typing import Set, Dict, List

def extract_config_fields_from_python(file_path: Path) -> Set[str]:
    """從 config.py 中提取所有配置欄位"""
    content = file_path.read_text(encoding='utf-8')
    
    # 找出所有 Field 定義
    field_pattern = r'(\w+):\s*[^=]*=\s*Field\('
    matches = re.findall(field_pattern, content)
    
    return set(matches)

def extract_env_vars_from_example(file_path: Path) -> Set[str]:
    """從 .env.example 中提取所有環境變數"""
    if not file_path.exists():
        return set()
        
    content = file_path.read_text(encoding='utf-8')
    
    # 找出所有環境變數定義
    env_pattern = r'^([A-Z_][A-Z0-9_]*)='
    matches = re.findall(env_pattern, content, re.MULTILINE)
    
    return set(matches)

def extract_env_vars_from_docker_compose(file_path: Path) -> Set[str]:
    """從 docker-compose.yml 中提取環境變數"""
    if not file_path.exists():
        return set()
        
    content = file_path.read_text(encoding='utf-8')
    
    # 找出所有 ${VAR} 格式的變數
    var_pattern = r'\$\{([A-Z_][A-Z0-9_]*)'
    matches = re.findall(var_pattern, content)
    
    # 找出 environment 區段中的變數
    env_pattern = r'^\s*-\s*([A-Z_][A-Z0-9_]*)='
    env_matches = re.findall(env_pattern, content, re.MULTILINE)
    
    return set(matches + env_matches)

def check_database_url_consistency(base_dir: Path) -> List[str]:
    """檢查 DATABASE_URL 的一致性"""
    issues = []
    
    # 檢查 config.py 中的默認值
    config_file = base_dir / "backend/app/core/config.py"
    if config_file.exists():
        content = config_file.read_text()
        if "@localhost:5432" in content and "@db:5432" not in content:
            issues.append(" config.py 中使用 localhost 而非 Docker 服務名 'db'")
        elif "@db:5432" in content:
            issues.append(" config.py 使用正確的 Docker 服務名 'db'")
    
    # 檢查 .env.example
    env_file = base_dir / ".env.example"
    if env_file.exists():
        content = env_file.read_text()
        if "DATABASE_URL=" in content:
            if "@db:5432" in content:
                issues.append(" .env.example 使用 Docker 服務名 'db'")
            elif "@localhost:5432" in content:
                issues.append(" .env.example 使用 localhost (應提供 Docker 和本地兩種選項)")
    
    return issues

def main():
    """主要檢查邏輯"""
    print(" 配置一致性檢查\n")
    
    base_dir = Path(".")
    config_file = base_dir / "backend/app/core/config.py"
    env_example = base_dir / ".env.example"
    docker_compose = base_dir / "docker-compose.yml"
    
    # 1. 檢查檔案存在
    print(" 檢查檔案存在性:")
    files_to_check = [
        (config_file, "config.py"),
        (env_example, ".env.example"), 
        (docker_compose, "docker-compose.yml")
    ]
    
    missing_files = []
    for file_path, name in files_to_check:
        if file_path.exists():
            print(f" {name}")
        else:
            print(f" {name} 不存在")
            missing_files.append(name)
    
    if missing_files:
        print(f"\n 缺少檔案: {', '.join(missing_files)}")
        return
    
    # 2. 提取配置欄位
    print(f"\n 提取配置欄位:")
    config_fields = extract_config_fields_from_python(config_file)
    env_vars = extract_env_vars_from_example(env_example)
    docker_vars = extract_env_vars_from_docker_compose(docker_compose)
    
    print(f"   config.py 欄位數: {len(config_fields)}")
    print(f"   .env.example 變數數: {len(env_vars)}")
    print(f"   docker-compose.yml 變數數: {len(docker_vars)}")
    
    # 3. 檢查 DATABASE_URL 一致性
    print(f"\n🔗 DATABASE_URL 一致性檢查:")
    db_issues = check_database_url_consistency(base_dir)
    for issue in db_issues:
        print(f"   {issue}")
    
    # 4. 檢查配置欄位映射
    print(f"\n 配置欄位映射檢查:")
    
    # 將 Python 欄位名轉換為環境變數名 (snake_case -> UPPER_CASE)
    expected_env_vars = set()
    for field in config_fields:
        env_name = field.upper()
        expected_env_vars.add(env_name)
    
    # 檢查缺少的環境變數
    missing_in_env = expected_env_vars - env_vars
    if missing_in_env:
        print(f"    .env.example 中缺少的變數:")
        for var in sorted(missing_in_env):
            print(f"      - {var}")
    else:
        print(f"    所有 config.py 欄位都在 .env.example 中")
    
    # 檢查多餘的環境變數
    extra_in_env = env_vars - expected_env_vars - docker_vars
    if extra_in_env:
        print(f"     額外的環境變數 (可能是 Docker 或前端專用):")
        for var in sorted(extra_in_env):
            print(f"      - {var}")
    
    # 5. Docker Compose 環境變數檢查
    print(f"\n🐳 Docker Compose 環境變數檢查:")
    docker_only = docker_vars - env_vars
    if docker_only:
        print(f"     只在 docker-compose.yml 中定義的變數:")
        for var in sorted(docker_only):
            print(f"      - {var}")
    
    env_only = env_vars - docker_vars - expected_env_vars
    if env_only:
        print(f"     只在 .env.example 中的變數:")
        for var in sorted(env_only):
            print(f"      - {var}")
    
    # 6. 總結
    print(f"\n 檢查總結:")
    total_issues = len([x for x in db_issues if "" in x]) + (1 if missing_in_env else 0)
    
    if total_issues == 0:
        print(f"    配置一致性檢查通過!")
    else:
        print(f"     發現 {total_issues} 個問題需要修正")
    
    print(f"\n 建議:")
    print(f"   1. 確保 DATABASE_URL 在 Docker 環境使用 'db:5432'")
    print(f"   2. 為本地開發創建 .env.local.example (使用 localhost)")
    print(f"   3. 確保所有 config.py 欄位都有對應的環境變數")
    print(f"   4. 定期運行此檢查確保配置同步")

if __name__ == "__main__":
    main()