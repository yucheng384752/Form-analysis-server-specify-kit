#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日誌分析工具
用於分析和監控 Form Analysis System 的日誌
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import argparse
from collections import defaultdict, Counter
import re

class LogAnalyzer:
    def __init__(self, log_dir=None):
        if log_dir is None:
            # 預設日誌目錄
            current_dir = Path(__file__).parent
            self.log_dir = current_dir.parent / "form-analysis-server" / "backend" / "logs"
        else:
            self.log_dir = Path(log_dir)
            
        self.app_log = self.log_dir / "app.log"
        self.error_log = self.log_dir / "error.log"
    
    def check_log_files(self):
        """檢查日誌檔案是否存在"""
        if not self.log_dir.exists():
            print(f" 日誌目錄不存在: {self.log_dir}")
            return False
            
        if not self.app_log.exists():
            print(f"  應用程式日誌不存在: {self.app_log}")
            return False
            
        return True
    
    def parse_json_log_line(self, line):
        """解析 JSON 格式的日誌行"""
        try:
            return json.loads(line.strip())
        except json.JSONDecodeError:
            # 如果不是 JSON 格式，嘗試解析純文字
            return {"message": line.strip(), "level": "unknown"}
    
    def get_recent_logs(self, hours=24):
        """獲取最近指定小時數的日誌"""
        if not self.app_log.exists():
            return []
            
        recent_logs = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with open(self.app_log, 'r', encoding='utf-8') as f:
            for line in f:
                log_entry = self.parse_json_log_line(line)
                
                # 嘗試解析時間戳
                timestamp_str = log_entry.get('timestamp')
                if timestamp_str:
                    try:
                        # 處理不同的時間格式
                        if 'T' in timestamp_str:
                            log_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            
                        if log_time >= cutoff_time:
                            recent_logs.append(log_entry)
                    except ValueError:
                        # 如果時間解析失败，仍然包含這個日誌
                        recent_logs.append(log_entry)
                else:
                    # 沒有時間戳的日誌也包含
                    recent_logs.append(log_entry)
        
        return recent_logs
    
    def analyze_error_patterns(self):
        """分析錯誤模式"""
        if not self.error_log.exists():
            return {"error_count": 0, "patterns": []}
            
        error_patterns = Counter()
        error_count = 0
        
        with open(self.error_log, 'r', encoding='utf-8') as f:
            for line in f:
                log_entry = self.parse_json_log_line(line)
                error_count += 1
                
                # 提取錯誤訊息關鍵字
                message = log_entry.get('message', '')
                if 'exception' in log_entry:
                    error_type = log_entry['exception'].split('.')[-1]
                    error_patterns[error_type] += 1
                elif 'error' in message.lower():
                    # 簡單的錯誤模式匹配
                    error_patterns['General Error'] += 1
                else:
                    error_patterns['Unknown'] += 1
        
        return {
            "error_count": error_count,
            "patterns": dict(error_patterns.most_common(10))
        }
    
    def analyze_api_usage(self):
        """分析 API 使用情況"""
        logs = self.get_recent_logs(hours=24)
        
        api_stats = {
            "upload": {"count": 0, "success": 0, "errors": 0},
            "query": {"count": 0, "success": 0, "errors": 0},
            "import": {"count": 0, "success": 0, "errors": 0}
        }
        
        performance_data = defaultdict(list)
        
        for log in logs:
            message = log.get('message', '').lower()
            level = log.get('level', '').lower()
            
            # 檔案上傳統計
            if '檔案上傳開始' in message or 'upload start' in message:
                api_stats["upload"]["count"] += 1
            elif '上傳完成' in message or 'upload complete' in message:
                api_stats["upload"]["success"] += 1
            elif '上傳錯誤' in message or 'upload error' in message:
                api_stats["upload"]["errors"] += 1
            
            # 查詢統計
            elif '查詢開始' in message or 'query start' in message:
                api_stats["query"]["count"] += 1
            elif '查詢完成' in message or 'query complete' in message:
                api_stats["query"]["success"] += 1
                
                # 提取處理時間
                time_match = re.search(r'(\d+\.?\d*)\s*ms', message)
                if time_match:
                    performance_data['query'].append(float(time_match.group(1)))
            
            # 匯入統計
            elif '匯入開始' in message or 'import start' in message:
                api_stats["import"]["count"] += 1
            elif '匯入完成' in message or 'import complete' in message:
                api_stats["import"]["success"] += 1
            elif '匯入錯誤' in message or 'import error' in message:
                api_stats["import"]["errors"] += 1
        
        # 計算平均處理時間
        avg_performance = {}
        for api, times in performance_data.items():
            if times:
                avg_performance[api] = {
                    "avg_ms": sum(times) / len(times),
                    "max_ms": max(times),
                    "min_ms": min(times),
                    "count": len(times)
                }
        
        return {
            "api_stats": api_stats,
            "performance": avg_performance
        }
    
    def generate_report(self):
        """生成完整的分析報告"""
        if not self.check_log_files():
            return
        
        print(" Form Analysis System - 日誌分析報告")
        print("=" * 50)
        print(f"📅 報告時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📂 日誌目錄: {self.log_dir}")
        print()
        
        # 檔案資訊
        print(" 日誌檔案資訊:")
        if self.app_log.exists():
            size = self.app_log.stat().st_size
            print(f"   📝 app.log: {size:,} bytes ({size/1024/1024:.2f} MB)")
            
        if self.error_log.exists():
            size = self.error_log.stat().st_size
            print(f"   🚨 error.log: {size:,} bytes ({size/1024/1024:.2f} MB)")
        print()
        
        # API 使用統計
        print(" API 使用統計 (過去24小時):")
        api_analysis = self.analyze_api_usage()
        
        for api_name, stats in api_analysis["api_stats"].items():
            success_rate = (stats["success"] / max(stats["count"], 1)) * 100
            print(f"   📡 {api_name.upper()}:")
            print(f"      總請求: {stats['count']}")
            print(f"      成功: {stats['success']}")
            print(f"      錯誤: {stats['errors']}")
            print(f"      成功率: {success_rate:.1f}%")
        print()
        
        # 效能統計
        if api_analysis["performance"]:
            print("⚡ 效能統計:")
            for api, perf in api_analysis["performance"].items():
                print(f"   🎯 {api.upper()}:")
                print(f"      平均處理時間: {perf['avg_ms']:.2f} ms")
                print(f"      最大處理時間: {perf['max_ms']:.2f} ms")
                print(f"      最小處理時間: {perf['min_ms']:.2f} ms")
                print(f"      樣本數: {perf['count']}")
            print()
        
        # 錯誤分析
        print("🚨 錯誤分析:")
        error_analysis = self.analyze_error_patterns()
        print(f"   總錯誤數: {error_analysis['error_count']}")
        
        if error_analysis["patterns"]:
            print("   錯誤類型分佈:")
            for pattern, count in error_analysis["patterns"].items():
                print(f"      {pattern}: {count}")
        print()
        
        # 最近活動
        recent_logs = self.get_recent_logs(hours=1)
        print(f"🕐 最近1小時活動: {len(recent_logs)} 條日誌")
        
        if recent_logs:
            print("   最新5條日誌:")
            for log in recent_logs[-5:]:
                timestamp = log.get('timestamp', 'N/A')
                level = log.get('level', 'INFO')
                message = log.get('message', '')[:80]
                print(f"      [{timestamp}] {level}: {message}")

def main():
    parser = argparse.ArgumentParser(description='Form Analysis System 日誌分析工具')
    parser.add_argument('--log-dir', help='日誌目錄路徑')
    parser.add_argument('--hours', type=int, default=24, help='分析最近N小時的日誌 (預設: 24)')
    parser.add_argument('--watch', action='store_true', help='即時監控模式')
    parser.add_argument('--errors-only', action='store_true', help='只顯示錯誤')
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(args.log_dir)
    
    if args.watch:
        print("📈 即時監控模式 (Ctrl+C 停止)")
        print("-" * 30)
        try:
            import time
            while True:
                recent = analyzer.get_recent_logs(hours=0.1)  # 最近6分鐘
                if recent:
                    for log in recent[-10:]:  # 顯示最新10條
                        timestamp = log.get('timestamp', 'N/A')
                        level = log.get('level', 'INFO')
                        message = log.get('message', '')
                        
                        if args.errors_only and level.lower() not in ['error', 'warning']:
                            continue
                            
                        print(f"[{timestamp}] {level}: {message}")
                
                time.sleep(5)  # 每5秒檢查一次
        except KeyboardInterrupt:
            print("\n停止監控")
    else:
        analyzer.generate_report()

if __name__ == "__main__":
    main()