-- 前端默认 Enterprise ID = 1；multipart_upload_sessions / documents 依赖 enterprises(id) 外键
INSERT INTO enterprises (id, name)
SELECT 1, 'Demo Enterprise'
WHERE NOT EXISTS (SELECT 1 FROM enterprises WHERE id = 1);

SELECT setval(
  pg_get_serial_sequence('enterprises', 'id'),
  COALESCE((SELECT MAX(id) FROM enterprises), 1)
);
