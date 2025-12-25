-- 創建 updated_at 觸發器

-- 創建觸發器函數
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 刪除舊觸發器（如果存在）
DROP TRIGGER IF EXISTS update_p3_items_updated_at ON p3_items;

-- 創建新觸發器
CREATE TRIGGER update_p3_items_updated_at
BEFORE UPDATE ON p3_items
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
