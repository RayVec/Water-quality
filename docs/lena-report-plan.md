# LENA Report 接入方案(Step 5 具体化)

> 对应 [multi-type-refactor.md](multi-type-refactor.md) 里悬而未决的第 5 步——"接入第二种类型"。设计稿已拿到(Figma: `Lena Report`,file key `vATBGxT1nPPmdEfCiIK1k6`,node `620:10810`,Cover + 14 个编号内容页),本文档基于对全部 15 个页面的逐页拆解给出实施计划。
>
> **现状:`report_types/lena/` 已在 `feature/lena-report-type` 分支上完成第一版实现**,15 页全部跑通(含双语),验证了第 1 节的结论——`engine/` 全程零改动。仍是未接入真实数据前的模拟版本:第 8 节的模拟数据源已经生效,机构目录(第 5 节)已经填入从 Figma 逐字提取的真实机构信息,图标是自制的占位简笔图标(非 Figma 原始图标导出)。

## 1. 结论:不变量成立,引擎本身不用改

15 个顶层 frame 宽度均为 **377px**,与 `PAGE_WIDTH_PX` 完全一致;每页高度不同(802~1602px),符合动态高度不变量。页面结构(深色 header/footer、页码、TOC 页的可点击链接、内容页 footer 的 "Return to table of contents" 链接)与 water_quality 现有的 `data-page` / `data-page-content` / `data-page-number` / `data-toc-entry` / `data-toc-page` 契约完全对得上。

**结论:`engine/` 目录不需要任何改动。** 这次是对"引擎是否真的类型无关"的第一次真实检验,目前看是通过的。所有工作都在 `report_types/lena/` 里完成。

## 2. 页面盘点(15 页)

| # | 标题 | 数据来源 | Figma node |
|---|------|---------|-----------|
| Cover | LENA Report | 纯静态 | 620:8898 |
| 1 | Table of Contents | 静态文案 + 页码(引擎生成) | 620:8928 |
| 2 | Overview(第1章) | **逐条记录数据** | 620:9037 |
| 3 | Detailed Results(第2章,统计卡+百分位图例) | **逐条记录数据**(图例本身静态) | 620:9160 |
| 4 | Detailed Results(逐指标结果+百分位仪表) | **逐条记录数据** | 620:9222 |
| 5 | Audio Environment(声音环境柱状图) | **逐条记录数据** | 620:9321 |
| 6 | Learn About Your Report(第3章,LENA背景+数据库) | 纯静态 | 620:9429 |
| 7 | (续)人口统计图表 + 14条育儿建议 | 纯静态 | 620:9565 |
| 8 | Resources(第4章,WCWH联系方式 + 育儿支持类第1组) | 静态/配置态 | 620:9778 |
| 9 | Resources(育儿支持类续) | 静态/配置态 | 620:9764 |
| 10 | Resources(育儿支持类续) | 静态/配置态 | 620:9826 |
| 11 | Resources(育儿支持类续) | 静态/配置态 | 620:9812 |
| 12 | Early Education | 静态/配置态 | 620:9840 |
| 13 | Access to Health Care | 静态/配置态 | 620:9859 |
| 14 | Access to Health Care(续,当前设计稿的最后一页) | 静态/配置态 | 620:9986 |

只有 **2、3、4、5 这四页**是真正逐条记录变化的数据页;6、7 是完全固定的科普内容;8~14 是一个可复用的"机构资源卡片"列表(名称/logo/简介/标签/联系方式),内容不随孩子变化,更像 water_quality 里 `config.json` 的 `waterUtilities` 那种配置态数据,而不是 Record 字段。

## 3. 新的 Record 字段(仅第 2~5 页需要)

对照 water_quality 的 Record 契约(`id`/`date`/`language` + 类型自有字段),LENA 至少需要:

```
child_name, birthday, age_at_recording, recording_date, recording_duration_hours
total_words_sounds, most_active_time
adult_words, child_vocalizations, conversational_turns
vocal_productivity                         # 页4提到但页3无对应计数,需和真实数据核对
{metric}_percentile   (child_vocalizations / conversational_turns / vocal_productivity)
{metric}_percentile_key   (Low / Low Average / High Average / High,可由百分位数在 analyze.py 里派生,不必要求源数据里就有)
audio_env_{category}_duration   (Noise / Silence-Background / Overlap / TV-Electronic / Speech / Distant Noise,6个数值,驱动第5页柱状图)
```

这份字段清单是从设计稿反推的,**还没有真实数据源核对过**——需要你提供 LENA 原始数据(Excel/CSV 或数据库导出 + 字段说明),才能定稿 `analyze.py` 里的字段名和计算逻辑(尤其是百分位数是源数据里现成的字段,还是要在 `analyze.py` 里用某个百分位对照表计算)。

## 4. 需要新增的模板组件(water_quality 词汇表里没有的)

- **儿童信息卡**(页2):姓名/生日/录音时年龄/录音日期/时长,一行一个小图标。
- **统计卡片**(页2):图标 + 标题 + 项目符号统计列表,重复 3 次(Child Vocalizations / Conversational Turns / Vocal Productivity)。
- **章节步骤条**(页3):橙色数字("2")两侧带装饰线——是章节标题的一种视觉变体,不是新机制,可以直接用 CSS 做。
- **百分位仪表**(页4):4 段配色的水平进度条,标记点位置由百分位数动态计算(`left: {percentile}%` 这类内联样式即可,不需要 JS/图片生成)。
- **音频环境柱状图**(页5):6 个竖直"药丸"形色块,高度按每类时长占比动态计算——同样可以用纯 CSS(`height` 内联样式)实现,不需要像 water_quality 的 `bar-gen.js` 那样用 Puppeteer 截图生成图片。**这点上 LENA 反而比 water_quality 更简单**,因为这两种图表都是简单几何形状,没必要走"生成图片再嵌入"这条路。
- **人口统计图表**(页7,饼图+环形图):内容固定(数据库口径,不随记录变化),**建议直接做成静态 SVG/图片素材**,不需要动态生成。
- **机构资源卡片**(页8~14):logo + 名称 + 简介 + 图标标签列表 + 米色联系信息面板(电话/邮箱/地址/外链,字段是否出现因机构而异,需要模板里做条件渲染)。这个组件在 8~14 页里循环出现约 12 次。

## 5. 静态内容从哪来:复用 `config.json` 的现有模式

水质报告的 `config.json` 里已经有 `waterUtilities` 这种"按名称查配置,而不是塞进每条 Record"的先例(见 [config.json](../report_types/water_quality/config.json))。LENA 的机构资源目录应该照搬这个模式:在 `report_types/lena/config.json` 里加一个 `resourceDirectory` 字段,按分类(Parenting Classes & Support / Early Education / Access to Health Care)存一个机构列表,模板里用 Jinja 循环渲染卡片,而不是让每条记录都携带一份机构列表。

**前提是这份机构列表本身不随孩子/家庭变化。** 需要你确认一下——见下方待确认事项。

## 6. 待确认事项 → 已确认

1. **机构资源目录(8~14页)是所有报告通用** ✅——整份列表直接放进 `config.json` 的 `resourceDirectory`,不做地区/语言筛选,不需要在 Record 里加地区字段。
2. **没有真实数据源** ✅——不等真实数据了。第 3 节的字段清单就是最终依据,由我模拟一份数据源(见第 8 节),先把全流程跑通;等真实数据到手后,只需要重写 `analyze.py` 的字段映射部分,Record 契约、模板、组件都不用动。
3. **类型 slug**:`lena`,即 `report_types/lena/`。
4. **图标/插画素材**:用 Figma MCP 的 `download_assets` 批量导出,不需要手动截图。

保留一条待办、但不阻塞当前实施:8~14 页在设计稿里到第14页仍未列完机构("Access to Health Care"分类还没收尾),但 Figma 原型里确实只有 15 个顶层 frame,没有第15页。当前按 Figma 现有页面 1:1 手工切页(跟 water_quality 一样是手写的固定页数);如果将来机构名单要频繁增减,会需要"按内容量动态决定页数"这个引擎当前不具备的能力,到时候再单独评估。

## 7. 模拟数据源(没有真实数据时的替代方案)

在真实数据到手之前,用下面这份反推的原始字段表模拟一份 `report_types/lena/data/lena_sample.xlsx`,`analyze.py` 按此解析。真实数据到手后,只需要改 `analyze.py` 里"读取原始列 → 填充这些字段"这一段,后面的百分位分档、年龄计算、模板渲染都不用动。

**原始列(模拟的 Excel 源文件)**

| 列名 | 类型 | 说明/取值范围 |
|------|------|--------------|
| `Participant_ID` | string | 沿用 water_quality 的 `id` 概念,格式 `L####`,例如 `L0142` |
| `Child_Name` | string | 儿童名字(仅名,不含姓,参照设计稿 "Hazel") |
| `Birthday` | date `MM/DD/YYYY` | 用于派生"录音时年龄" |
| `Recording_Date` | date `MM/DD/YYYY` | → Record 的 `date` |
| `Language` | `English`/`Spanish` | → Record 的 `language` |
| `Recording_Duration_Hours` | number | 12~24(真实 LENA 录音多为一整天佩戴时长) |
| `Total_Words_Sounds` | int | 800~3000 |
| `Most_Active_Time` | string | 例如 `"12:00 PM - 1:00 PM"` |
| `Adult_Words` | int | 5000~25000 |
| `Child_Vocalizations` | int | 200~3000 |
| `Conversational_Turns` | int | 50~800 |
| `Vocal_Productivity` | int | 每小时发声次数,50~200 |
| `Child_Vocalizations_Percentile` | int 1-99 | 假设源数据直接给百分位(真实 LENA 系统就是这么给的,不需要我们自己算) |
| `Conversational_Turns_Percentile` | int 1-99 | 同上 |
| `Vocal_Productivity_Percentile` | int 1-99 | 同上 |
| `AudioEnv_Noise_Pct` `AudioEnv_Silence_Pct` `AudioEnv_Overlap_Pct` `AudioEnv_TV_Pct` `AudioEnv_Speech_Pct` `AudioEnv_DistantNoise_Pct` | number,6列相加=100 | 驱动第5页音频环境柱状图 |

**`analyze.py` 里派生的字段**

- `age_at_recording`:由 `Birthday` 和 `Recording_Date` 算月龄,格式参照设计稿("23 months")。
- `{metric}_percentile_key`:按第3页图例的原始分档(**这是设计稿里写死的图例,不是我编的**)从百分位数映射文字——`1-24 → Low`,`25-49 → Low Average`,`50-74 → High Average`,`75-99 → High`。分档表放进 `config.json` 的 `percentileBands`,和 water_quality 用 `config.json` 存 `parameterRanges` 是同一个模式。
- `id` = `Participant_ID`,`date` = `Recording_Date` 转 `YYYY-MM-DD`。

**明确标注为占位、待真实数据核对的假设**:百分位数由源数据直接提供(而非我们计算)、`Vocal_Productivity` 的具体口径(次/小时)、`Recording_Duration_Hours` 的取值范围。这些一旦拿到真实数据不一致,只影响 `analyze.py` 内部逻辑,不影响 Record 契约字段名或模板。

## 8. 分步实施顺序

1. **脚手架**:创建 `report_types/lena/`(`config.json` 骨架、`report.html`/`report.css`、`mock.py`),确认 `run_pipeline.py` 能识别出新类型(`paths.available_types()` 自动发现,预期零改动)。
2. **数据驱动页面**(2~3~4~5页):按第7节的模拟数据源写 `analyze.py` + `mock.py`,把儿童信息卡/统计卡/百分位仪表/音频柱状图这几个新组件做出来。
3. **纯静态页面**:Cover、TOC、第6/7页——对着 Figma 截图逐像素抠 CSS。
4. **资源目录页面**(8~14页):把机构信息(第5节方案)放进 `config.json` 的 `resourceDirectory`,写模板循环。
5. **双语**:接入 `engine.translate`(纯配置,不需要改代码——只要 `report_types/lena/translations.xlsx` 存在即可复用现有逻辑)。
6. **全流程验证**:跑一次模拟批次,人工核对 PDF 与 Figma 设计稿的视觉还原度(因为没有"重构前基线"可比对,这次的验收标准是"跟设计稿对得上",不是 water_quality 那种像素级基线比对)。
7. **真实数据接入(未来)**:拿到真实数据源后,只重写 `analyze.py` 的字段映射部分,Record 契约、模板、组件都不用动。
