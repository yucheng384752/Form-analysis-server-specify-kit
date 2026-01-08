// P1 Production Date 格式化測試
// 將此代碼複製到瀏覽器 Console 中測試

console.log('=== P1 Production Date 格式化測試 ===\n');

// 測試函數（複製自 QueryPage.tsx）
function formatProductionDate(value) {
  if (!value) return '-';
  
  // 如果是數字（可能是 Excel 序列值或 YYMMDD 格式）
  if (typeof value === 'number') {
    const numStr = value.toString();
    if (numStr.length === 6) {
      const year = '20' + numStr.substring(0, 2);
      const month = numStr.substring(2, 4);
      const day = numStr.substring(4, 6);
      return `${year}-${month}-${day}`;
    }
  }
  
  // 如果是字串格式
  if (typeof value === 'string') {
    // 如果已經是 YYYY-MM-DD 格式，直接返回
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      return value;
    }
    
    // 如果是 YYMMDD 格式字串 (6位數字)
    if (/^\d{6}$/.test(value)) {
      const year = '20' + value.substring(0, 2);
      const month = value.substring(2, 4);
      const day = value.substring(4, 6);
      return `${year}-${month}-${day}`;
    }
    
    // 如果是 YYYY/MM/DD 或 YY/MM/DD 格式
    if (value.includes('/')) {
      const parts = value.split('/');
      if (parts.length === 3) {
        let year = parts[0];
        const month = parts[1].padStart(2, '0');
        const day = parts[2].padStart(2, '0');
        
        // 如果是兩位年份，補上 20
        if (year.length === 2) {
          year = '20' + year;
        }
        return `${year}-${month}-${day}`;
      }
    }
  }
  
  return value || '-';
}

// 測試案例
const testCases = [
  { input: 250717, expected: '2025-07-17', description: '數字格式 (YYMMDD)' },
  { input: '250717', expected: '2025-07-17', description: '字串格式 (YYMMDD)' },
  { input: '25/07/17', expected: '2025-07-17', description: '斜線格式 (YY/MM/DD)' },
  { input: '2025/07/17', expected: '2025-07-17', description: '完整斜線格式' },
  { input: '2025-07-17', expected: '2025-07-17', description: '標準格式（保持不變）' },
  { input: '25/7/17', expected: '2025-07-17', description: '單數字月日' },
  { input: null, expected: '-', description: '空值' },
  { input: '', expected: '-', description: '空字串' },
];

// 執行測試
let passed = 0;
let failed = 0;

testCases.forEach((test, index) => {
  const result = formatProductionDate(test.input);
  const success = result === test.expected;
  
  if (success) {
    passed++;
    console.log(` 測試 ${index + 1}: ${test.description}`);
  } else {
    failed++;
    console.log(`❌ 測試 ${index + 1}: ${test.description}`);
    console.log(`   輸入: ${JSON.stringify(test.input)}`);
    console.log(`   預期: ${test.expected}`);
    console.log(`   實際: ${result}`);
  }
});

console.log(`\n=== 測試結果 ===`);
console.log(`通過: ${passed}/${testCases.length}`);
console.log(`失敗: ${failed}/${testCases.length}`);
console.log(`成功率: ${((passed / testCases.length) * 100).toFixed(1)}%`);

// P3 批號解析測試
console.log('\n\n=== P3 批號解析測試 ===\n');

function parseP3LotNo(p3LotNo) {
  let baseLotNo = p3LotNo;
  let sourceWinder = null;
  
  const parts = p3LotNo.split('_');
  if (parts.length >= 2) {
    const lastPart = parts[parts.length - 1];
    if (/^\d{1,2}$/.test(lastPart)) {
      sourceWinder = lastPart;
      baseLotNo = parts.slice(0, -1).join('_');
    }
  }
  
  return { baseLotNo, sourceWinder };
}

const lotNoTests = [
  { input: '2503033_01_17', expectedBase: '2503033_01', expectedWinder: '17' },
  { input: '2503033_01_5', expectedBase: '2503033_01', expectedWinder: '5' },
  { input: '2503033_01', expectedBase: '2503033_01', expectedWinder: null },
  { input: '2503033', expectedBase: '2503033', expectedWinder: null },
];

console.log('批號解析測試:\n');
lotNoTests.forEach((test, index) => {
  const result = parseP3LotNo(test.input);
  const baseMatch = result.baseLotNo === test.expectedBase;
  const winderMatch = result.sourceWinder === test.expectedWinder;
  const success = baseMatch && winderMatch;
  
  if (success) {
    console.log(` 測試 ${index + 1}: ${test.input}`);
  } else {
    console.log(`❌ 測試 ${index + 1}: ${test.input}`);
    console.log(`   預期基礎批號: ${test.expectedBase}, 實際: ${result.baseLotNo}`);
    console.log(`   預期收卷機: ${test.expectedWinder}, 實際: ${result.sourceWinder}`);
  }
  console.log(`   -> 基礎批號: ${result.baseLotNo}, 收卷機: ${result.sourceWinder || '無'}\n`);
});

console.log('\n=== 測試完成 ===');
console.log('請在前端頁面實際操作驗證功能！');
