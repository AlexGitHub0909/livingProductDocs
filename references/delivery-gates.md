# 稳定交付阶段与门禁

## 完整性的定义

完整性必须绑定用户确认的范围。一个交付可以完整描述“当前版本的指定模块”，但不能据此宣称整个产品、所有环境或不可访问的外部系统均已覆盖。

完整终稿同时满足：

1. 范围明确，所有纳入和排除项可解释；
2. 项目拓扑已确认，不靠目录名称推断职责；
3. 范围内每个能力或流程都有证据链；
4. 请求的文档均已生成或更新；
5. 文档之间没有已知矛盾；
6. 阻塞最终结论的问题为零；
7. 当前工作区上的新鲜检查通过。

## 阶段 1：SCOPE

记录：

- 工作模式：`BASELINE`、`DELTA_SYNC`、`AUDIT` 或 `FOCUSED_UPDATE`；
- 产品或业务范围；
- 可访问仓库、分支、版本和环境；
- 请求的交付物及目标读者；
- 明确排除项；
- 是否允许修改、提交、远程同步或发布。这些权限分别判断。

门禁：范围足以判断哪些流程、入口和文档必须覆盖。用户没有指定文档目录时先沿用现有职责文件；没有现有体系时才建立最小目录。

## 阶段 2：DISCOVERY

先运行 `discover_project.py`，再人工核实：

- Git 和运行单元边界；
- manifest、workspace、构建、启动和部署配置；
- 页面、API、命令、任务、事件或报表入口；
- 业务编排、状态机、数据结构和外部依赖；
- 测试位置、测试类型和执行方式；
- 现有文档、索引、镜像和归档；
- 无法访问或无法读取的范围。

门禁：每个范围内运行单元至少抽样一条真实注册或调用关系。存在 `SCAN_INCOMPLETE`、未识别仓库、未确认生成代码来源或不可访问的关键组件时不能通过。

## 阶段 3：EVIDENCE

每个范围内流程建立最小证据链：

| 字段 | 要求 |
|---|---|
| 流程或能力 | 使用项目真实名称和稳定标识 |
| 产品意图 | 已确认目标；没有时明确为未知，不从代码反推 |
| 角色与前提 | 谁在什么条件下触发 |
| 入口 | 页面、API、事件、命令、任务或其它入口 |
| 执行 | 关键校验、编排、状态转换和外部调用 |
| 数据结果 | 字段、关系、状态、通知、审计或无持久化说明 |
| 异常与恢复 | 失败、超时、部分成功、重试和人工处理 |
| 权限与可见性 | 操作者、可见范围和敏感边界 |
| 测试 | 用例、自动化、人工验证和最近执行证据 |
| 文档 | 当前承载该事实的文档位置 |
| 状态 | `VERIFIED`、`IMPLEMENTED`、`PARTIAL`、`PLANNED`、`UNKNOWN`、`BLOCKED` 或 `OUT_OF_SCOPE` |

门禁：所有范围内流程都有记录；冲突已裁决或标成阻塞；代码存在不等于产品目标已确认；历史测试不等于当前版本通过。

## 阶段 4：DRAFT

按 `document-contracts.md` 更新用户请求的文档。优先修改现有职责文件，不复制事实到第二套文档。

门禁：

- PRD 的规则和验收标准可追溯到流程；
- 测试用例覆盖主路径、异常、边界、权限和状态转换；
- 数据字典以 schema 或等价事实为准；
- 手册使用真实入口、文案和操作顺序；
- 每份长期文档有本次版本记录；
- 未确认内容使用明确状态，不混入当前事实。

## 阶段 5：RECONCILE

逐项检查：

- PRD 验收标准是否都有测试用例；
- 状态、枚举、字段、默认值和权限是否跨文档一致；
- 手册动作是否能在真实入口中找到；
- 删除或重命名的能力是否仍残留；
- `PLANNED`、`PARTIAL`、`UNKNOWN` 是否在其它文档被写成已完成；
- 版本记录是否准确说明本次变化。

门禁：已知矛盾为零。不能裁决的冲突进入阻塞项。

## 阶段 6：FINAL_GATE

创建临时 JSON 交付清单并运行 `validate_delivery.py`。下面的路径和基线只是格式示例，实际使用时必须替换为当前项目中的真实值：

```json
{
  "status": "FINAL_COMPLETE",
  "scope": {
    "statement": "当前版本指定产品范围的交付文档",
    "baseline": "commit:0123456789abcdef",
    "roots": ["."],
    "included": ["用户确认的业务流程和入口"],
    "excluded": [],
    "requested_deliverables": [
      "product_requirements",
      "test_cases",
      "data_dictionary",
      "operations_manual"
    ]
  },
  "coverage": {
    "topology": {"status": "PASS", "evidence": ["file: path/to/discovery-report.json"]},
    "product_intent": {"status": "PASS", "evidence": ["file: path/to/approved-product-decision.md"]},
    "flows": {"status": "PASS", "evidence": ["file: path/to/flow-evidence-map.md"]},
    "interfaces": {"status": "PASS", "evidence": ["file: path/to/entry-inventory.md"]},
    "data": {"status": "PASS", "evidence": ["file: path/to/current-schema.sql"]},
    "tests": {"status": "PASS", "evidence": ["command: project-test-command (passed on YYYY-MM-DD)"]},
    "existing_documents": {"status": "PASS", "evidence": ["file: path/to/document-index.md"]}
  },
  "deliverables": [
    {
      "kind": "product_requirements",
      "path": "docs/product.md",
      "status": "COMPLETE",
      "contract_checks": {
        "audience_and_scope": "PASS",
        "flows_and_exceptions": "PASS",
        "rules_states_and_permissions": "PASS",
        "acceptance_and_gaps": "PASS"
      }
    },
    {
      "kind": "test_cases",
      "path": "docs/tests.md",
      "status": "COMPLETE",
      "contract_checks": {
        "case_traceability": "PASS",
        "executable_preconditions_and_steps": "PASS",
        "expected_results_and_data": "PASS",
        "negative_boundary_and_recovery": "PASS",
        "coverage_and_evidence": "PASS"
      }
    },
    {
      "kind": "data_dictionary",
      "path": "docs/data.md",
      "status": "COMPLETE",
      "contract_checks": {
        "entities_fields_and_types": "PASS",
        "constraints_and_relations": "PASS",
        "value_sources_and_writes": "PASS",
        "sensitivity_and_retention": "PASS",
        "migration_and_compatibility": "PASS"
      }
    },
    {
      "kind": "operations_manual",
      "path": "docs/manual.md",
      "status": "COMPLETE",
      "contract_checks": {
        "roles_and_entry": "PASS",
        "observable_fields_and_actions": "PASS",
        "ordered_steps_and_results": "PASS",
        "errors_recovery_and_handoff": "PASS",
        "applicability_and_version": "PASS"
      }
    }
  ],
  "open_items": [],
  "checks": {
    "topology_sampled": "PASS",
    "evidence_traceability": "PASS",
    "cross_document_consistency": "PASS",
    "version_records": "PASS",
    "writing_quality": "PASS",
    "fresh_validation": "PASS"
  }
}
```

覆盖维度没有界面、数据或其它适用对象时，可以使用 `NOT_APPLICABLE`，但必须给出 `reason`。不能用 `NOT_APPLICABLE` 隐藏尚未检查或无法访问的范围。

`evidence` 必须写实际文件、提交、决策记录、检查命令或执行结果。复制示例时要替换所有 `path/to/*`、示例提交和日期，不能保留占位值，也不能使用“已审查”“已确认”这类不可复核的文字。`contract_checks` 使用示例中的固定键，且请求交付物对应的检查必须全部为 `PASS`。脚本负责校验清单结构、文件存在和门禁状态；内容判断仍必须来自对实际证据的审阅，不能把自填清单当成证据本身。

## 失败时的稳定输出

门禁未通过时，不要只说“信息不足”。输出 `EVIDENCE_BLOCKED` 包：

1. 已确认的范围和版本；
2. 已完成的拓扑与流程证据；
3. 可以安全交付的草稿或已更新部分；
4. 每个阻塞项影响哪份文档和哪些结论；
5. 已检查过的位置和仍缺少的证据；
6. 需要用户回答的最少问题；
7. 获得答案后从哪个阶段恢复。

这也是稳定输出：它保证结论真实、可继续执行，而不是用推测补齐终稿。
