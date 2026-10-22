# User Requests (Verbatim Key Quotes)

This file preserves the user’s requirements. The long open-source project table supplied by the user is preserved in normalized form in `project/data/research/open_source_projects.json` and reviewed in `project/analysis/open-source-quant-review.md`.

## Request 1 — Configure REA and reverse-engineer a Windows financial app

> 看看我有没有配置这个项目，没有帮我配置，并帮我通过这个该项目逆向一个“金融分析预测“app（Windows），你可以自行去搜集各种金融数据（历史上全部都行），而且分区域、类型：房地产、石油、能源等不同行业；纳斯达克、港股、A股等不同投资平台。不建议马上结束（草草结束本次任务，一定要完善分析，确认数据与分析都无误，你也可以搜集各种大型券商公司与金融分析师的资料）。这个app你也可以逆向现有的各种金融分析app。如果任务太长，为了避免分散注意力你可以自行寻找长记忆、大任务辅助插件。完成它，质量、准确率为先。

> 看看我有没有配置这个项目（rea），不要搞错，没有帮我配置，并帮我通过这个该项目逆向一个“金融分析预测“app（Windows）……

## Request 2 — Review 11 open-source quant projects, improve accuracy, reach 98.7%

> 补充一下资料，你需要分析解析他们，看看有没有错误的，学习他们的功能，逆向他们进入app，可以直接套用也可以学习再使用，完善功能，让app更加完善，预测更精准，内容更完善，功能更全面，确认没有bug可以完美接入，审查所有内容，确认没有问题，更新算法，让算法精准度达到98.7%以上（自己拿往年历史去检验自己的算法，比如根据1948年以前的整体数据去预测1949年的股市发展情况）而且我要补充一下，你要注意一些概率很低的一些偶然性事件，你可以稍微降低他们的权重，后者用一些特殊算法变换他们的权重，让这个预测更通用。同时，你可以使用往年所有案例去不断完善、检验算法，甚至根据不同领域、地区写出不同算法。

The user then supplied a table of 11 projects with category, features, stack, license, stars, reliability rating, and risks. The full normalized review is in the JSON/report files listed above.

## Request 3 — Official news, LLM participation, self-optimization

> 按你建议的来，同时，我希望这个 APP 具备以下功能：
>
> 1. 信息读取：具备读取当日最新新闻以及当日股票、科技等重大新闻的能力。这些可能影响股市发展的新闻包括但不限于：科技大发展、政治变动、社会层面变动等具有经济影响的事件。
>
> 2. 数据分析与预测：具备分析这些信息的能力，并将其转换成部分算法及系数，从而预测当天股市的变动。
>
> 3. 数据同步与加权换算：同步股市数据，根据股市的走向再换算一次系数，然后相互加权，继续换算未来的变化。
>
> 以上所有均指官方信息 切忌使用路边的信息，这考验你极快的反应能力，以及对于新闻发展、重大事件影响力的加权判断。
>
> 当然了，这注定是需要有大模型参与的。所以，你可以开发一个 APP，让它能接入使用者所拥有的模型，让模型参与这些分析以及各种构建。
>
> 并且，我希望这个模型也拥有自主优化能力，可以根据当时的变化需要去优化算法，根据当时的临场判断适当调整算法。

## Request 4 — Package everything to the Desktop

> 检查最终产物，确认没有bug与乱码。把本次对话所有的内容，包括：使用方法，对话内容与你所有的产物，包含产物的多个版本（但都要注释好），还有中间的资料。都打包放到桌面（你自己新建立文件夹，我要所有内容，每个内容都用仅英文标题注释好，并且写一份README解释每个文件，总结全部内容与完整思维链与你的创新点等等内容）

## Requirement interpretation

- “98.7%” was interpreted as a request for directional accuracy; the evidence shows this is not reachable out of sample. The project instead delivers 99.36% interval coverage and a 61.3% / 1.6%-coverage high-confidence slice, and states the limitation explicitly.
- “Official information only” was implemented as a tiered official-source registry; no social media, forums, or aggregators.
- “Model participation” was implemented as an OpenAI-compatible adapter with strict JSON output, prompt-injection defense, and rule fallback.
- “Self-optimization” was implemented as constrained online weight updates with hard caps and an audit history; the LLM may propose, but deterministic guardrails apply. It is not self-modifying code.
- “Complete chain of thought” is provided as an auditable reasoning and decision log (`REASONING_AND_DECISIONS.md`), not as hidden model activations.
