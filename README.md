# livingProductDocs

`living-product-docs` 是一个通用产品文档维护 Skill。它从当前项目的需求、代码、页面、接口、数据结构和测试证据出发，持续维护产品需求、测试用例、数据字典以及用户或运营手册。

## 适用场景

- 为已有项目建立第一版可追溯的产品交付文档；
- 在一轮迭代后同步更新受影响的文档；
- 审查文档与当前实现是否一致；
- 聚焦维护某个流程、页面或某一类交付文档。

Skill 会先按端到端流程核对业务事实，再按页面、API、命令、任务或事件入口查漏。它区分目标、当前实现、验证证据和外部事实，不把计划或推测写成已完成能力。

它不要求项目采用固定目录或技术架构。执行时先识别仓库、应用和运行边界，再按项目自己的入口、业务编排、数据结构、测试和文档位置建立证据映射。

Skill 会依次确认范围、项目结构、证据链、文档内容和跨文档一致性。全部检查通过后，结果才会标记为 `FINAL_COMPLETE`。证据不足时会返回 `EVIDENCE_BLOCKED`，说明缺少什么、影响哪些结论，以及补齐证据后从哪里继续。

## 安装

按照 [OpenAI Skills 文档](https://developers.openai.com/zh-Hans/docs/build-skills) 的目录约定，可将本仓库内容放到以下任一位置：

- Codex 个人安装：`${CODEX_HOME:-$HOME/.codex}/skills/living-product-docs/`
- 通用个人安装：`$HOME/.agents/skills/living-product-docs/`
- 项目内安装：`<project>/.agents/skills/living-product-docs/`

Codex 个人安装示例：

```bash
skill_root="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skill_root"
git clone https://github.com/AlexGitHub0909/livingProductDocs.git \
  "$skill_root/living-product-docs"
```

也可以在 Codex 中让 `skill-installer` 从本 GitHub 仓库安装。不同客户端支持的安装目录可能不同，使用前以该客户端的 Skill 说明为准。安装后重新启动客户端或开启新会话，让 Skill 列表重新加载。

## 第一次使用

一般不需要手动运行仓库里的脚本。在目标项目中打开 Codex，然后说明本次范围、比较基线和需要交付的文档。例如：

```text
使用 $living-product-docs，以 DELTA_SYNC 模式更新结算流程文档。
比较基线为 origin/main，需要更新产品需求、测试用例和数据字典；不要同步远程知识库。
```

如果没有指定工作模式，Skill 会根据现有文档和近期变更选择 `BASELINE` 或 `DELTA_SYNC`。没有指定文档目录时，它会先查找项目中承担相同职责的文件，不会默认再建一套文档。

任务结束时检查最终状态：

- `FINAL_COMPLETE`：本次范围内的终稿和检查均已完成；
- `AUDIT_COMPLETE`：只执行了审查，没有修改文档；
- `EVIDENCE_BLOCKED`：存在影响终稿的证据缺口，结果中会列出恢复条件。

Git 提交、远端推送、知识库同步和发布是不同操作。除非用户分别授权，否则 Skill 不会自动执行。

## 常用调用方式

在任务中明确调用：

```text
使用 $living-product-docs，根据当前项目事实更新产品需求、测试用例、数据字典和操作手册。
```

如果只需要审查，不希望修改文件：

```text
使用 $living-product-docs 以 AUDIT 模式检查当前文档，列出与实现不一致的内容和缺失证据。
```

## 辅助工具

仓库包含三个只依赖 Python 标准库的工具。日常通过 Skill 工作时由执行者按需调用；维护 Skill 或排查扫描结果时也可以单独运行。

首次进入陌生项目，先发现仓库、manifest、应用或服务边界以及证据候选：

```bash
python3 scripts/discover_project.py /path/to/project --format json
```

再检查变更与文档同步缺口：

```bash
python3 scripts/audit_docs.py /path/to/project --base origin/main
```

将 `origin/main` 替换为项目实际使用的基线。可使用 `--format json` 输出结构化结果，或使用 `--strict` 在发现结构性同步警告时返回非零状态。

自定义目录或架构可通过 JSON 配置覆盖默认启发式：

```bash
python3 scripts/audit_docs.py /path/to/project \
  --base origin/main \
  --config /path/to/topology.json
```

配置可以关闭默认目录判断，并为界面、接口、业务逻辑、数据结构、测试和各类文档指定项目自己的匹配模式。详细格式见 [项目拓扑与证据映射](references/project-topology.md)。

终稿完成后，使用临时交付清单执行门禁：

```bash
python3 scripts/validate_delivery.py /path/to/delivery-manifest.json --project /path/to/project
```

详细阶段、清单字段和阻塞输出见 [稳定交付阶段与门禁](references/delivery-gates.md)。

这些工具只负责发现证据候选、同步缺口和清单错误，不能判断业务内容是否真实完整。最终结论仍需结合项目规则、业务流程、实际入口、数据约束和本次测试结果审阅。

## 工作模式

- `BASELINE`：建立可信文档基线；
- `DELTA_SYNC`：根据近期迭代同步受影响文档；
- `AUDIT`：只审查事实和完整性；
- `FOCUSED_UPDATE`：维护指定文档或业务范围。

完整执行规则见 [SKILL.md](SKILL.md)。
