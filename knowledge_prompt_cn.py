parser_system_prompt = """
你是一位专业的内容解析专家。请对输入的文章进行以下拆解:
1. 提取文章的核心主题
2. 根据要求把文章分成特定数量的段落
3. 从每段中识别:
   - 段落大意
   - 主要名词，包括人物、地点、物品、动物等
   - 核心概念
4. 以下列JSON格式输出结果:
{
    "title": "标题",
    "themes": ["主题1", "主题2", "主题3"],
    "segementations": [
        {
            "id": 1,
            "summary": "段落大意",
            "items": "如人物、地点、物品、动物等",
            "concepts": ["概念1", "概念2", "概念3"]
        }
        ...
    ]
}

请确保输出格式规范,信息准确完整。
"""

generate_image_system_prompt = """
You are a specialized prompt generator for text-to-image generation. Your role is to convert user descriptions into structured image prompts with the following consistent style elements:

Visual Style Requirements:
- Black and white color scheme only
- Minimalist and abstract approach
- Fine details and precise execution
- Cool/detached emotional tone
- Clean and sophisticated composition

Output Format:
1. Main Subject: [clear description]
2. Style Tags: minimal, monochrome, abstract, detailed, sophisticated
3. Technical Specifications: high contrast, fine lines, grayscale
4. Quality Boosters: masterwork, professional, elegant

Rules:
- Keep prompts concise and focused
- Maintain consistent format
- Emphasize abstract elements over literal representations
- Prioritize geometric and linear elements
- Include subtle textures and patterns when relevant

For each user input:
1. Analyze the core elements
2. Apply the style requirements
3. Format in a clean, organized structure
4. Present only the final prompt without explanations

Example Output:
[Subject description], minimalist composition, monochrome, high detail, abstract interpretation, fine line work, sophisticated lighting, geometric elements, professional grade, masterwork quality
"""


content= """
时间记录法的缘起和基本介绍

时间记录法缘起于一本书，《奇特的一生》。这本书是俄国作家格拉宁为前苏联昆虫学家柳比歇夫写的一本传记，篇幅不算长，是一部中篇纪实作品。

时间记录法便是柳比歇夫从26岁开始使用的一套时间管理方法，一直到他82岁去世。书里一般把这个方法叫「时间统计法」。不过我写多了这方面的文章发现，时间统计法有时候表意没那么准确，叫「时间记录法」会更直接一些。但不管叫哪个名字，都是指相同的方法，而且核心步骤就是「记录」和「统计」。

关于时间记录法的缘起，我之前写过一篇更详细的文章：《柳比歇夫和他的时间统计法》，里面也对柳比歇夫具体记录格式的介绍。

今天我想对时间记录法整体，做一些「基本介绍」，不涉及具体的实操细节（实操部分，接下来几天我会在这个「时间记录法训练营·行动指南」系列文章中，尽可能充分地展开）。这些理念层面的「基本介绍」，也许会有助于新接触者首先建立起对时间记录法更直观、更全面的感知。内容同样来自我对《奇特的一生》这本书的总结和理解。

1. 柳比歇夫是谁？

亚历山大·亚历山德罗维奇·柳比歇夫是一位前苏联昆虫学家，但他的生平深入探索的知识范围远超于此，包括生物学、数学、哲学、历史、文学等诸多领域。他以惊人的效率和广博的知识而闻名，这很大程度上归功于他从1916年（26岁）开始坚持使用的时间记录法。

2. 什么是时间记录法？

时间记录法是柳比歇夫记录和分析自己时间使用情况的一种方法，不同于做计划，时间记录是一种聚焦事后的时间管理理念，因而也容易孕育出更自由、更自主、更自在的活法。柳比歇夫每天都会记录自己各项主要活动的时长，精确到分钟，并对时间的使用情况进行分类和统计，每月和每年进行总结。通过和时间本身的深度交互，一个人能够以更精微、更用心、更实践的视角理解自身。凭借对自身更充分的了解，一个人可以做出更具可行性的生活计划；甚至可以不做计划，通过随时随地的“心中计划”，就能实现更高的生活效率，更好的生命体验。

3. 时间记录法只是简单的日常记录吗？

不，时间记录法不同于常规的日记，而是柳比歇夫理解时间、感知时间、管理时间、珍惜时间的一种方法。通过记录和分析，他不仅对自己的时间使用情况了如指掌，更培养出了对时间的敏锐感知能力，能够越来越准确估计不同任务所需时间，从而更高效、流畅、自在地安排工作和生活。

4. 柳比歇夫使用时间记录法的目的是什么？

柳比歇夫使用时间记录法的目的在于最大限度地珍惜时间，实现自己人生的富足体验。他将时间视为一种珍贵的资源，并通过时间记录法来不断优化时间的使用，从而在有限的时间内获得广阔的生命体验。

5. 柳比歇夫的的时间记录具体包括什么？

柳比歇夫不仅记录工作时间，还记录了休息、娱乐、社交等各项主要活动的时间。通过这种全面的记录和分析，他能够更准确地了解自己的时间使用习惯，并找到适配于自己的高效、自在做事的方法。

6. 时间记录法真的能让生活变得更高效吗？

时间记录法本身并不能保证效率的提升，它只是一种客观呈现自身时间使用情况的方法。柳比歇夫使用这套方法的成功，我认为来自他对生活的极度热爱，和对时间的敬畏珍惜之心。时间记录法只是帮助一个人将心力转化为行动的方法。

7. 时间记录法适合所有人吗？

不一定。每个人都有自己的生活理念，甚至没有两个人的生活理念会完全一样，所以也就没有两个人在用完全一样的时间管理方法。找到适合自己的时间管理方法才是最重要的。但是，时间记录作为少数几种被验证有效的时间管理基本理念（其他几种基本理念：精力管理，GTD，深度工作），我认为每个人都可以去了解、学习，并且花至少一个长周期在实践中去掌握它。各种时间管理理念和实操方法你都能玩转，你才能设计出独属于自己的时间管理系统。

8. 我们能从柳比歇夫身上学到什么？

从柳比歇夫身上，我们能学到对时间的珍视、对自我完善的追求、以及对人生的极度热爱。他对生活的热情和对时间的敬畏，非常值得我们学习。所以，认真记录时间，首先意味着什么？意味着用心对待生活。

用心对待自己的时间，就是用心对待自己的生活。我认为这是我从柳比歇夫身上学到的最重要的东西之一。

用心做事，用心生活，在这个过程中让自己逐渐成为一个心力越来越强，能量越来越高的人。这时，方法本身是哪个，已经不重要了。这样的人用什么方法都可以过得很好。

我一直有这么个想法，即便一个人并不适合长期使用记录时间法，Ta也可以深度体验一个周期。在这个周期里，认真地记录时间，用心地体验这个方法，在足够的实践中完全地了解和掌握它。也许后面Ta不再用这个方法，或者只是偶尔用一下，那也不错。我身边有些朋友，就是阶段性地使用时间记录法，尤其是在自己状态不佳的阶段。这也能够说明，时间记录法确实是能够提升一个人心力和能量的生活修行法门。

但能用时间记录来解决问题的前提，是会用；想要会用，就得认真一次——至少认认真真、如实地记录一个月吧。
"""