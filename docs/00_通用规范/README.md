# 通用规范

## 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.13 | 主开发语言 |
| AI 模型 | DeepSeek API | 中文理解力强，成本低 |
| 输出格式 | Obsidian Markdown | frontmatter + wikilink |
| HTTP | requests | 调用 AI API |
| 文本提取 | 直读(txt) / ebooklib(epub) / pymupdf(pdf) | 多格式支持 |

## 代码规范

1. **命名**：函数/变量用 snake_case，类用 PascalCase
2. **注释**：中文注释，关键逻辑必须注释
3. **类型标注**：函数参数和返回值加类型提示
4. **错误处理**：AI 返回异常时有 fallback，不崩溃
5. **配置**：API key 等敏感信息存环境变量或 config.py，不硬编码

## 目录规范

```
src/                ← 所有源代码
vault/              ← Obsidian 输出（自动生成，不要手动改）
data/input/         ← 待分析文本
data/state/         ← AI 分析中间状态（JSON）
docs/               ← 项目文档
```

## 提交规范

- 每次只改一个模块
- 改完必须测试（跑一个真实文本验证）
- commit message：`模块名: 做了什么`
