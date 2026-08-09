# 多类型报告引擎 —— 改造方案

把当前的水质专用管线，改造成一个「报告引擎 + 若干报告类型」的结构，使新增一种数据类型的报告
只需要写它自己的数据处理、可视化和模板，不必碰引擎。

> **现状：第 0~4 步已在 `refactor/multi-type-engine` 分支上实施完成**，每步单独提交、逐像素验证
> 通过（含真实批次核对）。第 5 步（接入第二种类型）仍按原计划等设计稿到手后再做。实施过程中发现
> 并修正的具体问题记在第 6 节对应步骤和第 3 节的命名说明里，不是本文档最初设计的一部分。

## 0. 前提：四个已确认的不变量

在设计契约之前先钉死这次讨论确认下来的东西，因为它们直接决定引擎层的边界该划多宽：

- **粒度不变**：还是「一条 record → 一份 PDF」，不是多条记录拼一份，也不是一条记录出多份。
- **双语不变**：还是英语/西班牙语两种，不需要做成通用 i18n。
- **交互不变**：PDF 内部还是纯超链接（跳到文档内部锚点，或跳到外部网址），没有表单、没有 PDF
  内嵌脚本、没有回传到任何系统。
- **版式不变**：所有类型都是同一个手机宽度的单栏版式（现在是 377px），每一页的高度按内容自适应
  ——宽度统一是为了让用户在不同报告之间切换、在手机上滚动阅读时体验一致；高度自适应是水质报告
  已经在用的机制，不是新能力。

这四条不是猜的，是确认过的。它们的意义是：引擎层（分页、翻译、目录、版式尺寸、PDF 产出）的能力
边界基本可以定型，不需要为「以后可能一份 PDF 对应多条记录」「以后可能要支持十种语言」「以后可能
要换一套完全不同的页面尺寸」这类假设预留空间——那种预留在只有一个真实样本时几乎总是猜错方向。
真正会变的只有固定宽度以内的设计：版面布局、颜色、图标、文案、图表画法、数据处理逻辑。

## 1. 现状盘点：代码里哪些东西已经通用，哪些是水质专属的

不凭空归类，直接读代码得出的结论。

**已经是通用的（零水质知识）**

- [height_calculation.py](../height_calculation.py) 全文 98 行：接收 HTML 路径 + CSS + 一组
  element id，用共享的 headless Chrome 量出每个元素的渲染高度，没有一处提到参数、水厂或任何
  水质概念。这部分不用改，直接归入引擎层。
- `run_pipeline.py` / `settings.py` 的编排模式（manifest 文件 + 一个环境变量把三个阶段串起来）
  本身也不含水质知识，只是目前只有 batch 一个维度，缺一个 type 维度。

**形状通用、但目前手写得脆弱的（引擎该管、还没管好的）**

- [templates/template.html](../templates/template.html) 里 18 个 `<article>`（toc + page2~page17）
  几乎逐页复制同一套外壳：顶部 `.header` 放页码和标题，`.content` 放正文，底部 `.header` 再放一次
  页码和「返回目录」链接。这套外壳的*存在*是任何「手机形状、每节一页、页眉页脚都要显示当前页码」
  的报告都需要的机制，跟具体设计无关——但现在页码是手写死的文本。page5 里就有一处真实的不一致：
  顶部页眉写的是 `6`（[template.html:788](../templates/template.html#L788)），底部页脚写的是 `5`
  （[template.html:818](../templates/template.html#L818)），而这个 `<article>` 的 id 是 `page5`。
  这正是手写页码这种「结构账本」会自然产生的错误，不是假设出来的风险。
- 目录（`#toc`）同理：26 条 `.heading1` / `.heading2` 每条都手写死了目标页码（`2` `3` `4` …），
  并用 `{% if 'Lead' in display_parameters %}` 这种模板条件去猜某个参数缺失时目录要不要少一条、
  后面页码要不要跟着往前挪——这一步完全没有自动化，全靠写模板的人手算。
- [templates/report.css](../templates/report.css) 里 17 条按页面 id 写的
  `@page { height: ...px }` 规则（toc + page2~page17），值本身还会被
  [report_gen.py:451](../report_gen.py#L451) 的正则在每次渲染时原地改写成 Selenium 实测的高度——
  也就是说这份 CSS 文件里的数字其实是假的，真值是运行时算出来再回写进去的。这套机制（量高度→回写
  `@page`）本身是通用的，任何「每节一页、页高自适应内容」的报告都要做这件事；但目前是用正则去匹配
  `@page pageN {` 这种字符串模式，前提是 CSS 里的页面 id 命名跟今天一致，换一套设计后这个假设未必
  站得住。
- [templates/report.css](../templates/report.css) 的 `:root` 和 `@page` 里写死了
  `width: 377px`——这是所有类型都要遵守的手机宽度，不是水质专属的设计选择，但现在没有任何机制
  保证以后的类型会用同一个值。类型自己的 CSS 还是要写这一行（不共享 CSS 文件，见第 2 节非目标），
  只是这个数值不再是每个类型随便选，而是要跟引擎里的统一值一致，由 `validate()` 检查（见 5.2）。

**彻底水质专属的**

- [config.json](../config.json) 的 `parameterRanges` / `parameterTypes` / `parameters` /
  `columnMap` / `barDefaults` / `waterUtilities`——从头到尾是水质词汇表。
- [data_analysis.py](../data_analysis.py)：Hornsense ID 映射、按 `Flush_type`（Outdoor/FF）和
  `Filter_softener_none` 分组、按消毒剂类型分 cohort 算社区均值、`Disinfectant` 虚拟参数解析——
  这是水质这一种报告类型独有的数据语义，换一种数据类型这些逻辑整个不成立。
- [bar-gen.js](../bar-gen.js) 782 行：「渲染阶段生成一批数据驱动的图片资源」这个*步骤*是通用模式，
  但这个文件里具体画的——313px 宽的刻度条、圆点标记、绿/黄双色范围、四种参数类型（0/1/2/3）各自
  的标签排布逻辑——全部是这一种设计独有的视觉语言。换一种设计很可能连「要不要预渲染图片」这个前提
  都不成立（也可能换成完全不同的图表方式，甚至不需要图片，纯 CSS/HTML 由 WeasyPrint 直接画）。
- [report_gen.py](../report_gen.py) 里目前仍有四处水质知识残留在「引擎」文件里：
  [`_process_record_parameters()`](../report_gen.py#L107)、
  [Sample_date 解析](../report_gen.py#L592)、[water_utility 查表](../report_gen.py#L594)、
  [latest_annual_report_year](../report_gen.py#L266)。
- [settings.py](../settings.py) 的 `available_batches()` 硬编码 `glob("*.xlsx")`，`resolve()`
  硬编码 `f"{batch}.xlsx"`——引擎层目前假设输入必然是 Excel，这个假设放错了位置：应该由每个类型
  自己决定输入格式，引擎不该管。

## 2. 目标与非目标

**目标**

- 引擎与报告类型彻底分离：新增一种类型，只写它自己的数据处理、可视化、模板，不改引擎代码。
- 用语义标记（不是 CSS 类名）让引擎找到「这是一页」「这是页码位」「这是目录条目」——类名是设计
  的一部分，设计会完全不一样，共享类名约定必然锁不住。
- 消灭手写的结构账本：页码、`@page` 高度、目录页码，这三处目前都要人手动对齐，改造后全部由引擎
  从渲染结果算出来。
- 每一步都产出逐像素不变的 PDF，可独立验收、可独立回滚。

**非目标**

| 不做 | 原因 |
|---|---|
| 共享 base.html/base.css | 设计（版面、颜色、图标、文案）会完全不一样；共享标记只会变成新类型的枷锁——统一的页面宽度不算在内，那是第 0 节确认过的不变量 |
| 共享视觉组件库 | 同上，`parameter_box` 这类宏应该留在水质类型包内部，不升级成「引擎组件」 |
| 强制「组件生成」步骤必须是 Python 函数、或必须存在 | bar-gen.js 现在是 Node/Puppeteer，未来类型也可能完全不需要这一步；具体契约见 5.3 |
| 替换 WeasyPrint | 交互仍是纯超链接，WeasyPrint 的变高命名页能力仍是唯一需要的能力 |
| 现在就为「第二种类型」写扩展点 | 原因见第 0 节——现在只确认了四个不变量，其余全是未知，提前设计扩展点一定是猜的 |

## 3. 目标形态

```
engine/                          零水质知识
    paths.py                     type + batch → 全部路径（今天的 settings.py，加一个 type 维度）
    pipeline.py                  编排 analyze → components(可选) → render
    render.py                    Jinja 渲染 → 翻译 → 分页/目录/空页处理 → WeasyPrint → 落盘
    translate.py                 DOM 替换 + 词表查找；在线翻译兜底+回写缓存（沿用现有 googletrans 机制）。
                                  公共词表合并逻辑留到真的出现第二种类型再加（见第 9 节）
    pagination.py                今天的 height_calculation.py，原样搬入，零改动
    layout.py                    页码生成、@page 生成、目录页码回填、空页删除——全部基于属性契约，不认类名
    validate.py                  契约校验：模板不满足契约就报错退出

data/
    reference/                   跨类型共用的数据。目前只有 Participant_Hornsense_ID_Map.xlsx——
                                  已确认同一批 WCWH 研究参与者，不同报告类型共用同一份身份映射，留在这里不用动
    sources/<type>/<batch>.*      各类型自己的输入批次，扩展名和内部格式完全由该类型的 analyze() 解释，引擎不假设是 Excel

report_types/water_quality/
    config.json                  今天的 config.json 原样搬入，新增一个 output 小节（文件名规则，见 5.3）
    analyze.py                   今天的 data_analysis.py，出口新增 id/date/language 三个字段
    components/                  今天的 bar-gen.js 原样搬入，外面包一层引擎能调用的入口（可以就是"跑这个 node 脚本"）
    mock.py                      预览用假数据（今天 run_pipeline.py 里的 build_template_record）
    translations.xlsx            该类型专有词汇
    assets/                      水质专属图标图片和字体（今天 assets/ 下的全部内容）
    templates/report.html        report.css   照设计稿自由编写，只需要标出语义属性

build/<type>/<batch>/            生成物
reports/<type>/<batch>/          交付 PDF
```

命名两点说明（实施 Step 4 时发现，不是最初设计）：

- **目录不叫 `types/`，叫 `report_types/`。** `types` 是 Python 标准库自己的模块名——用它做包名会导致
  `import types` 永远解析成标准库那个（Python 启动时就把它放进了 `sys.modules` 缓存），本地包里的
  `report_types.water_quality.*` 因此永远无法通过 `types.water_quality` 这条路径访问到。这条不是本方案
  的核心决定，纯粹是给一个通用词让了路。
- **没有单独的顶层 `assets/`。** 原计划里字体等"证明跨类型共用"的东西放顶层 `assets/`，图标图片放类型自己
  的 `assets/`。实施时发现，在只有一个类型的情况下没有任何证据支持"字体也跨类型共用"这个假设——这本身
  就是一处不该现在就做的预留。现在字体和图标图片一起放在 `report_types/water_quality/assets/` 里；等第
  二种类型真的出现，如果它也要用同一套字体，再决定要不要拆出一个共用位置（同第 9 节"不提前建空目录"的
  原则）。

依赖方向单向向下，无环：

```
                  engine/pipeline
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
  report_types/*/analyze   report_types/*/components  engine/render
        │                │                │  └→ translate / pagination / layout / validate
        └────────────────┴────────────────┘
                         ▼
                  engine/paths
```

## 4. 使用流程：改造后怎么生成、怎么修改一份报告

这一节说的不是怎么改代码，是第 6 节的步骤全部做完之后，日常「跑一批真实数据」「调一个设计」「加
一种新类型」这几件事分别要做什么，尽量做到不需要读引擎代码就能完成。改造过程中（第 0~3 步），
命令行的使用方式还是今天这样，不会先变差再变好。

### 场景 A —— 日常生成一批报告（最常见的操作）

命令不变：

```bash
.venv/bin/python run_pipeline.py
```

流程比今天多一步「选类型」，但只有一种类型存在的这段时间里，这一步会像今天「只有一个 batch 时
自动选中」一样自动跳过——所以在第二种类型真正出现之前，日常操作体验跟今天完全一样：

```
请选择报告类型:
  1. water_quality
✅ 自动选择类型: water_quality        ← 只有一种类型时自动选中，不用问

请选择要执行的流程:
  1. 完整流程（真实数据）
  2. 模板预览（假数据，用于调设计）
> 1

Available batches in data/sources/water_quality/:
  1. B8 Data
  2. B9 Data
> 1

✅ 完成。报告在 reports/water_quality/B8 Data/
```

给单个阶段手动传参数的用法也保留，只是 manifest 里多一个 type 字段：

```bash
MANIFEST='build/water_quality/B8 Data/manifest.json' .venv/bin/python report_gen.py
```

### 场景 B —— 设计一份报告，完全不用等真实数据

不管是调整现有类型的设计，还是从零做一种新类型，「模板预览」都能让你在没有真实数据、不用碰
`analyze.py` 的情况下反复看 PDF 长什么样：

```
请选择报告类型: <type>
请选择要执行的流程: 2 (模板预览)
✅ 完成。报告在 reports/<type>/template/
```

每次改完 `templates/report.html` / `report.css`，重新跑一次这条命令，几秒钟就能看到新 PDF。这是
今天水质类型「模式 3」已经在用的流程；改造后每个类型天生就有这个能力，不需要为它额外开发。

### 场景 C —— 修改一个已有报告类型

不用碰 `engine/`，只改 `report_types/<type>/` 里面的东西：

| 想改什么 | 改哪个文件 | 怎么验证 |
|---|---|---|
| 版式、文案、颜色、图标 | `templates/report.html` / `report.css` | 场景 B 的预览流程 |
| 一个参数的达标范围、图表画法 | `config.json` | 预览流程 + 跑一个真实 batch 对比结果 |
| 数据怎么从原始文件变成一条 record | `analyze.py` | 跑一个真实 batch，检查 `records.json` |
| 西语翻译不准 | `translations.xlsx` 对应行的 Spanish 列 | 改完重新生成西语报告即可，不用碰代码 |

翻译有个特别之处：某句英文文案第一次出现、词表里还没有对应词条时，引擎会自动调用 Google 翻译一次
并把结果写回这份表格——第一次生成某句新文案的西语报告时，那句话可能是机翻的；发现不准，直接去表格
里把 Spanish 列那一格改掉，之后所有报告都会用你改过的版本。

### 场景 D —— 接入一种全新的报告类型

等设计稿到手、真的要做第二种类型时，按这个顺序走：

1. `mkdir report_types/<type>`，写这种类型自己的 `config.json`。
2. 照设计稿写 `templates/report.html` + `report.css`，宽度用第 0 节统一的手机宽度，高度不用管
   （引擎按内容自动算）；此外只需要在恰当位置加上 5 个 `data-*` 属性（见第 5 节契约）。
3. 写 `mock.py`：手造一条假数据，跑场景 B 的预览流程，把设计调对——这一步完全不需要真实数据，
   也不需要 `analyze.py` 写完。
4. 设计调对之后再写 `analyze.py`，把真实数据源变成 record 列表；只需要保证每条 record 有
   `id` / `date` / `language` 三个字段，其余字段这个类型自己定，引擎不关心。
5. 如果这种报告需要预渲染图片（图表之类），写 `components`；不需要就完全跳过这一步。
6. 把一批真实数据放进 `data/sources/<type>/`，跑场景 A 的完整流程。

第 3 步就能看到 PDF，不用等第 4 步的数据管道写完——这是设计和数据处理解耦之后才能做到的：今天
这两件事绑在同一份 `run_pipeline.py` / `report_gen.py` 里，改一处经常牵动另一处。

这个过程理论上不需要碰 `engine/` 一行代码。如果做到某一步发现非改引擎不可，说明契约本身有缺口，
回头看第 9 节待定事项，先补契约再继续，不要在引擎里为这一种类型加特例。

## 5. 契约

这几份是引擎与类型之间**仅有的**接口，除此之外类型内部随意。

### 5.1 Record 契约（引擎只认三个字段）

| 字段 | 类型 | 引擎用它做什么 |
|---|---|---|
| `id` | str | 输出文件名、产物目录名 |
| `date` | str，`YYYY-MM-DD` | 输出文件名、产物目录名 |
| `language` | `"English"` \| `"Spanish"` | 决定要不要过翻译、文件名前缀 |

约定：这三个字段必须在 `analyze()` 里直接产出，写进 `records.json`，不能等渲染时才现算——第 1
节提到的那几处「渲染时才计算」的字段（日期、年份）搬到这里，不是新增工作量，只是挪个位置，顺带
让 `records.json` 变成一份自洽、不依赖运行时刻的产物。

### 5.2 模板属性契约

引擎在渲染完的 HTML 里要认识 5 个 `data-*` 属性（`data-page` 的取值 `"toc"` 是特例，用来单独
标记目录页）：

| 属性 | 位置 | 用途 |
|---|---|---|
| `data-page` | 每页的最外层容器 | 枚举页面，按文档顺序编号 |
| `data-page="toc"` | 目录页 | 识别目录页，跳过它自己的空页判断 |
| `data-page-content` | 页内内容区 | 判空；空则整页删除 |
| `data-page-number` | 页眉页脚里显示页码的元素 | 写入最终页码——一页里有几个这样的元素就写几处 |
| `data-toc-entry="<锚点id>"` | 目录里一条条目 | 目标页被删则整条删除；否则填页码 |
| `data-toc-page` | 条目内放页码的子元素 | 写入目标页页码 |

标签、类名、嵌套结构、样式全部自由，比如：

```html
<section data-page>                  <!-- 标签、类名随便，引擎只认这个属性 -->
  <header class="随便什么设计">
    <span data-page-number></span>   <!-- 引擎写页码，样式引擎不管 -->
  </header>
  <div data-page-content>
    <!-- 这一页的全部内容，怎么排都行 -->
  </div>
</section>
```

今天的 [`remove_empty_pages_and_update_toc()`](../report_gen.py#L503) 已经是这个思路的雏形——
DOM 遍历、判空、删空页、重新编号、回填目录——只是它认的是这套设计专属的类名
（`div.header span.number`、`.headings .heading1`、`.title a`、`.page`）。把选择器从类名换成
属性，逻辑基本不用重写，风险主要在「换选择器时会不会选漏」，这也是为什么这一步要单独验收
（见第 6 节）。

`validate()` 渲染后检查：至少一个 `data-page`；每个 `data-page` 恰好一个 `data-page-content`；
每个 `data-toc-entry` 的锚点在文档里真实存在；页面宽度等于第 0 节确认的统一宽度。不满足就报错
退出，不静默继续。

### 5.3 类型包契约

| 名称 | 形式 | 说明 |
|---|---|---|
| `analyze(source, config) -> list[dict]` | 函数 | 唯一数据入口；`source` 是一个不透明字符串/路径，类型自己决定怎么解释（Excel、CSV、多文件都行） |
| `components(records, out_dir, config)` | 可选（不提供则跳过） | 生成该类型需要的图片等产物；内部想 subprocess 到任何语言都行，引擎不关心 |
| `mock(config) -> dict` | 函数 | 预览模式用的单条假数据 |
| `templates/report.html` + `report.css` | 文件 | 遵守 5.2 的属性契约 |
| `config.json` | 文件 | 该类型全部配置，包含输出文件名规则 |

文件名规则进类型 config，不再硬编码 `WATER` / `AGUA`：

```jsonc
"output": {
  "filename": "{prefix}.{id}.{date}.pdf",
  "prefix": { "English": "WATER", "Spanish": "AGUA" },
  "dateFormat": "%Y.%m.%d"
}
```

## 6. 分步实施

每一步独立可交付、独立可验证、独立可回滚。做完任一步项目都能正常出 PDF。

**第 0 步 —— 验证工具入库（前提，不是可选项）**

把「渲染结果没变」这件事变成能自动跑的东西：

- `tests/cases.py` —— 覆盖英/西、有无过滤水样、缺参数、全部超标/达标、两种消毒剂等场景，全部用
  假数据构造（跟 `run_pipeline.py` 模板预览用的是同一套机制），不放真实参与者数据
- `tests/compare_dom.py` —— HTML 规范化后逐节点对比
- `tests/compare_pdf.py` —— PDF 页数、每页纸张尺寸、逐像素对比
- `tests/baseline/` —— 上面这些假数据场景的当前输出，作为基线提交进仓库

没有这一步，后面每一步都没法证明「没改坏」。目前 repo 里没有 `tests/`，这是唯一必须先做的事。

*验收：上面列出的场景都能生成 PDF、无报错；`tests/baseline/` 有内容且已提交。*

**第 1 步 —— 统一 Record 契约**

把第 1 节列出的、[report_gen.py](../report_gen.py) 里残留的四处水质知识下沉进
[data_analysis.py](../data_analysis.py) 的 `analyze()`；同时把 `run_pipeline.py` 里 84 行的假
数据构造（`build_template_record` + `_metric_block`）挪进类型自己的 `mock.py`。

*验收：`records.json` 字段变多，PDF 逐像素不变。*

**第 2 步 —— 钩子从类名换成 `data-*` 属性**

改模板 18 个 `<article>`、内容区、页码位、26 条目录条目；`report_gen.py` 里的选择器同步换；加
`validate()`（含 5.2 里的页面宽度检查）。

*验收：PDF 逐像素不变。这一步风险最高——选择器换错会让空页判断或页码悄悄失效而不报错，必须靠
逐像素对比兜底，不能靠肉眼看。*

**第 3 步 —— `@page` 与目录页码改成引擎生成**

删掉 [report.css](../templates/report.css) 里 17 条手写 `@page`，删掉 `report_gen.py` 里的正则
改写；目录页码改成从 `data-toc-entry` / `data-toc-page` 生成，模板里不再手写 `2` `3` `4` 这些
占位数字。

*验收：PDF 逐像素不变；CSS 变短；模板里不再有手写页码。*

**第 4 步 —— 物理拆分 `engine/` 与 `report_types/water_quality/`**

纯搬文件 + 改 import，不改逻辑。同时把 `settings.py` 的 `available_batches()` / `resolve()`
松开 Excel 假设，给路径和 manifest 加 type 维度。

*验收：PDF 逐像素不变。*

**第 5 步 —— 接入第二种类型（等设计稿到手后再做）**

新建 `report_types/<type>/`，照设计稿写模板，实现 `analyze` / `components` / `mock`。这一步引擎大概率
还要再调整——这是预期内的，而且现在只有一个真实消费者，调整代价很低。

## 7. 风险

| 风险 | 对策 |
|---|---|
| 选择器换成属性时选漏，空页/页码判断悄悄失效 | 第 2 步单独成步，靠逐像素对比兜底，不靠人工检查 |
| 引擎生成的 `@page` 跟手写规则有细微差异 | 第 3 步先并行生成、跟现有 CSS diff，确认一致再删手写版本 |
| 契约按只有一个类型的经验定的，第二种类型一来就撞破 | 契约刻意做薄（3 个 record 字段 + 5 个属性），原因见第 0 节；真撞破了就在第 5 步现场改，只有一个消费者时代价最低 |
| `components` 步骤语言不统一（今天是 Node，以后可能是别的） | 契约不规定运行时（见 5.3）；水质类型继续 subprocess 到 node，跟今天等价 |
| 翻译环节的在线兜底（googletrans）是非官方逆向库，容易失效 | 这是既有行为，不在这次改造范围内新增或收窄；`engine/translate.py` 原样继承这个特性，只是挪了位置 |

## 8. 工作量（粗估）

| 步骤 | 估计 |
|---|---|
| 0 验证工具入库 | 0.5 天 |
| 1 统一 Record 契约 | 1 天 |
| 2 换属性钩子 | 1~1.5 天 |
| 3 引擎生成 `@page`/目录 | 1.5 天 |
| 4 物理拆分 | 1 天 |
| **合计（不含第二种类型）** | **约 5~5.5 天** |

第 1~3 步即使第二种类型永远不出现也划算：它们消灭了两处纯人工维护的账本，也让渲染结果不再依赖
「渲染的那一刻是几点」。

## 9. 待定事项

- **公共词表要不要现在就建。** 现在只有一份类型词表，不存在「公共」的东西，`translate.py` 也
  不需要合并逻辑。等第二种类型真的出现、且真的有词汇要共用时，再决定共用词表放在哪、哪些词进去
  ——不提前建一个空文件占位。
- **第二种类型的设计稿到手后，第一件事是回头检查 5.2 的属性是否够用**——尤其是「目录」这个概念
  本身是否还存在（如果新类型的报告很短、不需要目录，`data-page="toc"` 这条钩子可能整个不会触发，
  这是可以接受的，只需要确认引擎在「没有 toc 页」时不会报错）。
