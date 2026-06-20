# 字典

系统术语和错误码定义。

## 术语表

| 术语 | 含义 |
|------|------|
| Vault | Obsidian 知识库目录 |
| Frontmatter | Markdown 文件头部的 YAML 元数据 |
| Wikilink | Obsidian 的 `[[链接]]` 格式 |
| Graph View | Obsidian 的关系图谱可视化 |
| Character Card | 人物卡片，包含人物的所有信息 |
| Setting Card | 设定卡片，世界观/地点/势力的描述 |

## 错误码

| 错误 | 含义 | 处理 |
|------|------|------|
| FILE_NOT_FOUND | 输入文件不存在 | 检查路径 |
| ENCODING_ERROR | 文件编码无法识别 | 尝试 utf-8/gbk/gb2312 |
| AI_PARSE_FAIL | AI 返回内容无法解析为 JSON | 检查 data/state/ 原始响应 |
| API_ERROR | DeepSeek API 调用失败 | 检查 API key 和网络 |
