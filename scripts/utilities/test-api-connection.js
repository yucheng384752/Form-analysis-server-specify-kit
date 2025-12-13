#!/usr/bin/env node

/**
 * 前端 API 連接測試腳本
 */

const axios = require('axios');

const API_BASE_URL = 'http://localhost:8000';

async function testApiConnection() {
    console.log(' 測試前端到後端 API 連接...\n');
    
    const endpoints = [
        { name: '健康檢查', url: '/healthz' },
        { name: '日誌檔案列表', url: '/api/logs/files' },
        { name: '日誌統計', url: '/api/logs/stats' },
        { name: '日誌內容', url: '/api/logs/view?limit=5' }
    ];
    
    for (const endpoint of endpoints) {
        try {
            console.log(` 測試: ${endpoint.name} (${endpoint.url})`);
            const response = await axios.get(`${API_BASE_URL}${endpoint.url}`, {
                timeout: 5000,
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            });
            
            console.log(` 成功 - 狀態碼: ${response.status}`);
            
            if (endpoint.url === '/healthz') {
                console.log(`   回應: ${JSON.stringify(response.data, null, 2)}`);
            }
            
        } catch (error) {
            console.log(` 失敗 - ${endpoint.name}`);
            console.log(`   錯誤: ${error.message}`);
            
            if (error.response) {
                console.log(`   狀態碼: ${error.response.status}`);
                console.log(`   回應: ${JSON.stringify(error.response.data, null, 2)}`);
            } else if (error.request) {
                console.log(`   網路錯誤: 無法連接到 ${API_BASE_URL}`);
            }
        }
        
        console.log('');
    }
    
    console.log('🏁 測試完成');
}

// 檢查是否安裝了 axios
try {
    require('axios');
    testApiConnection();
} catch (error) {
    console.log(' 需要安裝 axios 套件: npm install axios');
    console.log('或者使用 curl 命令測試:');
    console.log('curl -X GET http://localhost:8000/healthz');
    console.log('curl -X GET http://localhost:8000/api/logs/files');
}