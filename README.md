# livingProductDocs

`living-product-docs` 是一个通用产品文档维护 Skill。它从当前项目的需求、代码、页面、接口、数据结构和测试证据出发，持续维护产品需求、测试用例、数据字典以及用户或运营手册。

## 适用场景

- 为已有项目建立第一版可追溯的产品交付文档；
- 在一轮迭代后同步更新受影响的文档；
- 审查文档与当前实现是否一致；
- 聚焦维护某个流程、页面或某一类交付文档。

Skill 会先按端到端流程核对业务事实，再按页面、API、命令、任务或事件入口查漏。它区分目标、当前实现、验证证据和外部事实，不把计划或推测写成已完成能力。

它不要求项目采用固定目录或技术架构。执行时先识别仓库、应用和运行边界，再按项目自己的入口、业务编排、数据结构、测试和文档位置建立证据映射。

## 安装

按照 [OpenAI Skills 文档](https://developers.openai.com/zh-Hans/docs/build-skills) 的目录约定，可将本仓库内容放到以下任一位置：

- 个人安装：`$HOME/.agents/skills/living-product-docs/`
- 项目安装：`<project>/.agents/skills/living-product-docs/`

也可以在 Codex 中让 `skill-installer` 从本 GitHub 仓库安装。安装后重新启动相关客户端或开启新会话，使 Skill 列表重新加载。

## 使用

在任务中明确调用：

```text
使用 $living-product-docs，根据当前项目事实更新产品需求、测试用例、数据字典和操作手册。
```

如果只需要审查，不希望修改文件：

```text
使用 $living-product-docs 以 AUDIT 模式检查当前文档，列出与实现不一致的内容和缺失证据。
```

## 辅助扫描器

仓库包含一个只依赖 Python 标准库的证据扫描器：

```bash
python3 scripts/audit_docs.py /path/to/project --base origin/main
```

可使用 `--format json` 输出结构化结果，或使用 `--strict` 在发现结构性同步警告时返回非零状态。

自定义目录或架构可通过 JSON 配置覆盖默认启发式：

```bash
python3 scripts/audit_docs.py /path/to/project \
  --base origin/main \
  --config /path/to/topology.json
```

配置可以关闭默认目录判断，并为界面、接口、业务逻辑、数据结构、测试和各类文档指定项目自己的匹配模式。详细格式见 [项目拓扑与证据映射](references/project-topology.md)。

扫描器只负责识别证据候选和可能遗漏，不能证明文档已经完整。最终结论仍需结合项目规则、业务流程、页面行为、数据约束和实际测试结果人工核对。

## 工作模式

- `BASELINE`：建立可信文档基线；
- `DELTA_SYNC`：根据近期迭代同步受影响文档；
- `AUDIT`：只审查事实和完整性；
- `FOCUSED_UPDATE`：维护指定文档或业务范围。

完整执行规则见 [SKILL.md](SKILL.md)。
