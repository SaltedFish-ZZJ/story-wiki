# 代码质量优化计划

> 日期：2026-06-23
> 基于：代码审查发现的 Bug 和技术债

---

## 修复清单

### P0 — 会崩溃的 Bug（3 项）

| # | 文件 | 问题 | 修复方案 |
|---|------|------|----------|
| 1 | `analyzer.py:701` | `format()` 花括号注入 — context 含 `{` 时 KeyError | 用 `str.replace()` 替代 `.format()` |
| 2 | `chapter_generator.py:499` | 硬编码 `total_chapters = 12` — 生成非 12 章时大纲映射错误 | 接收调用方传入的实际章数 |
| 3 | `plot_generator.py:606-607` | `.get() or default` 吞掉 falsy 值 — temperature=0 无效 | 改用 `.get(key, default)` |

### P1 — 功能不一致（2 项）

| # | 文件 | 问题 | 修复方案 |
|---|------|------|----------|
| 4 | `chapter_generator.py:259` | 字数用 `len()` — 和 quality_checker 的中文分词不一致 | 复用 `_count_words` 逻辑 |
| 5 | `create.py:30` | `seed` 参数声明了但未使用 | 移除参数和 CLI 引用 |

### P2 — 死代码清理（2 项）

| # | 文件 | 问题 | 修复方案 |
|---|------|------|----------|
| 6 | `plot_generator.py:671-706` | `_parse_response` 与 `utils.py` 完全重复且未调用 | 删除方法 |
| 7 | `analyzer.py:8` | `import re` 导入后从未使用 | 删除导入 |

---

## 验证

```bash
python -m pytest tests/ -v
```

确认 223 个测试全部通过。
