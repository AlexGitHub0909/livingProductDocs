# 项目拓扑与证据映射

## 目的

不同项目可能采用单体、单仓多应用、多仓库、插件化、事件驱动、服务化或自定义分层。目录名称只能提供线索，不能证明模块职责。更新文档前先建立本次任务所需的拓扑，确认业务能力实际从哪里进入、执行、存储和验证。

## 发现顺序

### 1. 确认边界

先识别：

- Git 根、嵌套仓库、子模块和当前工作树；
- workspace、solution、module 或 package 声明；
- 构建、启动、部署和环境编排配置；
- 独立应用、服务、函数、插件、共享库和数据工程目录；
- 无法访问的外部仓库或系统。

不要因为多个模块处于同一仓库就假定它们共用状态、发布周期或数据源，也不要因为当前工作区只有一个仓库就断言完整流程都在其中。

存在多个独立 Git 根时，分别在各根目录运行变更扫描，再按业务流程合并证据；不要用父目录的一次 Git diff 代替所有子仓库状态。

### 2. 按运行关系识别职责

对每个与任务相关的运行单元，沿真实连接关系定位：

| 需要确认的事实 | 可用线索 |
|---|---|
| 启动与装配 | manifest、启动命令、入口文件、依赖注入、模块注册 |
| 用户或系统入口 | 路由表、导航、协议定义、命令注册、事件订阅、定时任务 |
| 业务规则 | use case、service、handler、domain、workflow 或等价编排代码 |
| 数据事实 | schema、migration、模型、序列化、事件结构、存储适配器 |
| 外部依赖 | 客户端封装、契约、消息主题、webhook、配置项 |
| 验证证据 | 单元、集成、契约、端到端、fixture、验收记录 |
| 交付文档 | 文档索引、知识库映射、手册、需求、测试集、数据字典 |

职责名称按项目实际语言记录。不要要求项目为了适配本 Skill 改目录或分层。

### 3. 建立任务级映射

映射至少包含：

| 组件或能力 | 仓库/根目录 | 入口 | 业务实现 | 数据 | 测试 | 现有文档 | 状态 |
|---|---|---|---|---|---|---|---|
| 项目实际名称 | 可访问边界 | 页面/API/事件等 | 实际位置 | 实际位置或外部系统 | 实际位置 | 实际位置 | 已确认/部分/未知 |

这是执行过程中的工作底稿，不默认创建新的长期文档。项目已有架构索引、模块清单或文档路由时，直接复用并核实；只有用户要求或项目规则要求时才持久化新映射。

### 4. 抽样验证

在批量扫描前，从每类组件选择一个代表性入口，沿调用、注册或消息关系追到业务实现、数据结果和测试。出现以下情况时，修正映射后再继续：

- 文件路径命中了规则，但运行时并未加载；
- 业务实现通过代码生成、插件注册或配置装配，不能从目录直接判断；
- 测试位于独立仓库或使用非标准命名；
- 文档描述的是目标架构，而当前实现仍在旧位置；
- 同一路径混有源码、生成物、归档或第三方代码。

## 扫描器配置

扫描器接受可选 JSON 配置。路径相对于被扫描项目根目录匹配，大小写不敏感。

```json
{
  "use_default_heuristics": false,
  "use_default_ignores": true,
  "ignore_patterns": [
    "generated/**",
    "archive/**"
  ],
  "category_patterns": {
    "interface": ["modules/storefront/templates/**"],
    "api": ["modules/gateway/contracts/**"],
    "behavior": ["capabilities/**/workflow.*"],
    "data_structure": ["storage/definitions/**"],
    "tests": ["verification/**"],
    "product_docs": ["knowledge/product/**"],
    "manuals": ["knowledge/operations/**"],
    "data_dictionary": ["knowledge/data/**"]
  }
}
```

执行：

```bash
python3 scripts/audit_docs.py /path/to/project \
  --base origin/main \
  --config /path/to/topology.json
```

可用分类为：`source`、`interface`、`api`、`behavior`、`data_structure`、`tests`、`documentation`、`product_docs`、`manuals` 和 `data_dictionary`。

- 保留 `use_default_heuristics: true` 时，自定义模式补充默认识别；
- 设置为 `false` 时，只保留通用文档、源码和测试识别及自定义模式，适合非标准架构；
- 默认跳过常见依赖、构建和生成目录；如果项目恰好把这些名称用于一方源码，可将 `use_default_ignores` 设为 `false`，再用 `ignore_patterns` 精确排除无关内容；`.git` 始终跳过；
- `ignore_patterns` 应排除生成物、第三方代码和归档，不应用来隐藏尚未核实的业务模块；
- 配置只是扫描辅助，不证明分类正确。最终仍须通过入口注册、依赖关系或运行证据核实。

如果需要把配置写入项目，先沿用项目已有配置目录和命名规则；没有持久化需求时使用临时文件，不为 Skill 新建平行配置体系。
