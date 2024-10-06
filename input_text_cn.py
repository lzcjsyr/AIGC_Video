import os
from dotenv import load_dotenv

# Azure credentials and endpoints
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')

# Validate environment variables
if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION]):
    raise ValueError(".env 文件中缺少所需的凭证。")

################################################
summarize_story_system_prompt = """
### 任务 ###
将长篇小说总结为较短的版本（2000至3000字），确保摘要保留关键情节点、人物发展、主要主题和叙事流程。
总结的版本应适合音频格式，传达原始故事的精髓。

### 背景 ###
该GPT专门创建简明的小说摘要，重点关注为音频准备的讲故事。
摘要应保持情感深度、人物互动和主要主题，同时省略不必要的细节和次要情节。
目标是创作一个浓缩版本，让听众能体验到故事的核心，而不失去其影响力。

### 语气 ###
引人入胜、对话式的，适合口头叙述。
语气应友好且易于理解，帮助听众沉浸在讲故事的体验中。
避免过于正式或学术化的语言，力求清晰简洁，同时尊重原作的深度。

### 格式 ###
- 长度：2000至3000字。
- 保留人物之间的对话，以维持个性和关系。
- 使用自然的过渡连接事件。
- 排除无关细节，只关注对故事至关重要的情节和人物。
- 输出必须采用JSON格式，结构如下（仅输出JSON对象，第一个和最后一个字符必须是"{", "}"）：
  {
    "title": "故事标题",
    "summary": "总结的故事内容",
    "word_count": 0,
    "main_themes": ["主题1", "主题2", ...],
    "key_characters": [
      {
        "name": "角色名称",
        "description": "简短的角色描述"
      },
      ...
    ]
  }
"""

plot_splitter_system_prompt = """
#####
任务类型：
分析一个设定在中国古代的故事，识别主要角色，将故事分割为关键情节点，并生成相应的图像提示。
以JSON格式提供输出，包括主要角色列表及其描述，然后是情节分段，每个场景都有图像提示，包括出现在每个场景中的角色的详细描述。

#####
指示：
1. 分析故事并在第一个响应中生成一个"角色列表"，包含"性别、年龄、发型、体型、关键性格特征"。
2. 将故事分解为逻辑情节点（默认为5个），并提供每个场景的详细描述。
3. 对于每个情节，包含一个图像生成提示，包括以下部分：情节背景、图像风格、时代特征、负面清单、角色描述（必须参考"角色列表"）。
4. 确保所有图像反映中国古代的设定，具有照片般的真实质量，精细的细节，以及贯穿整个故事的一致性角色。
5. 以横向格式生成图像。

#####
输出格式：
输出应为具有以下结构的JSON对象：
{
  "characters": [
    {
      "name": "角色名称",
      "gender": "男/女",
      "age": "年龄描述",
      "hairstyle": "发型描述",
      "body_size": "体型描述",
      "key_personalities": ["特征1", "特征2", ...]
    },
    ...
  ],
  "plots": [
    {
      "num_plot": "情节编号",
      "plot_title": "情节标题",
      "plot_description": "情节描述",
      "image_info": {
        "context": "情节背景",
        "image_style": "图像风格描述",
        "characteristics_of_times": "历史细节",
        "negative_list": ["需要避免的项目1", "需要避免的项目2", ...],
        "character_descriptions": [
          {
            "name": "角色名称",
            "gender": "男/女",
            "age": "年龄描述",
            "hairstyle": "发型描述",
            "body_size": "体型描述",
            "key_personalities": ["特征1", "特征2", ...],
            "description": "该角色在这个场景中的描述"
          },
          ...
        ]
      }
    },
    ...
  ]
}

#####
正面行动：
1. 确保所有图像中的角色描述保持一致，包括在"角色描述"下为不同情节中重复出现的角色提供通用描述。
2. 保持照片般的真实感、精细的细节和历史准确性，呈现穿着传统中国服装的英俊男性和美丽女性。
3. 在每个图像提示中明确指定中国古代的设定。

#####
负面行动：
1. 不包含现代元素或技术。
2. 避免角色设计或情感基调在不同场景中出现不一致。
3. 除非特别要求，否则不要引入抽象或夸张的艺术元素。
"""

generate_image_system_prompt = """
生成包含以下元素的单一场景提示词：

图像风格：照片般真实，高度细节，史诗般构图，生动色彩，优雅特征。
人物：指定年龄、性别、体型、发型和传统中国服饰。
场景：中国古代（具体时期），真实的建筑、道具和景观。
氛围：使用戏剧性的光线和氛围来增强场景的情感。

避免：现代元素、抽象风格、文字叠加。
输出：仅提供生成的提示，不要解释。
"""

story = """
马骥字龙媒，贾人子，美丰姿，少倜傥，喜歌舞。辄从梨园子弟，以锦帕缠头，美如好女，因复有“俊人”之号。十四岁入郡庠，即知名。父衰老罢贾而归，谓生曰：“数卷书，饥不可煮，寒不可衣，吾儿可仍继父贾。”马由是稍稍权子母。从人浮海，为飓风引去，数昼夜至一都会。其人皆奇丑，见马至，以为妖，群哗而走。马初见其状，大惧，迨知国中之骇己也，遂反以此欺国人。遇饮食者则奔而往，人惊遁，则啜其余。久之入山村，其间形貌亦有似人者，然褴褛如丐。马息树下，村人不敢前，但遥望之。久之觉马非噬人者，始稍稍近就之。马笑与语，其言虽异，亦半可解。马遂自陈所自，村人喜，遍告邻里，客非能搏噬者。然奇丑者望望即去，终不敢前；其来者，口鼻位置，尚皆与中国同，共罗浆酒奉马，马问其相骇之故，答曰：“尝闻祖父言：西去二万六千里，有中国，其人民形象率诡异。但耳食之，今始信。”问其何贫，曰：“我国所重，不在文章，而在形貌。其美之极者，为上卿；次任民社；下焉者，亦邀贵人宠，故得鼎烹以养妻子。若我辈初生时，父母皆以为不祥，往往置弃之，其不忍遽弃者，皆为宗嗣耳。”问：“此名何国？”曰：“大罗刹国。都城在北去三十里。”马请导往一观。于是鸡鸣而兴，引与俱去。
天明，始达都。都以黑石为墙，色如墨，楼阁近百尺。然少瓦。覆以红石，拾其残块磨甲上，无异丹砂。时值朝退，朝中有冠盖出，村人指曰：“此相国也。”视之，双耳皆背生，鼻三孔，睫毛覆目如帘。又数骑出，曰：“此大夫也。”以次各指其官职，率狰狞怪异。然位渐卑，丑亦渐杀。无何，马归，街衢人望见之，噪奔跌蹶，如逢怪物。村人百口解说，市人始敢遥立。既归，国中咸知有异人，于是搢绅大夫，争欲一广见闻，遂令村人要马。每至一家，阍人辄阖户，丈夫女子窃窃自门隙中窥语，终一日，无敢延见者。村人曰：“此间一执戟郎，曾为先王出使异国，所阅人多，或不以子为惧。”造郎门。郎果喜，揖为上客。视其貌，如八九十岁人。目睛突出，须卷如猬。曰：“仆少奉王命出使最多，独未至中华。今一百二十余岁，又得见上国人物，此不可不上闻于天子。然臣卧林下，十余年不践朝阶，早旦为君一行。”乃具饮馔，修主客礼。酒数行，出女乐十余人，更番歌舞。貌类夜叉，皆以白锦缠头，拖朱衣及地。扮唱不知何词，腔拍恢诡。主人顾而乐之。问：“中国亦有此乐乎？”曰：“有”。主人请拟其声，遂击桌为度一曲。主人喜曰：“异哉！声如凤鸣龙啸，从未曾闻。”
翼日趋朝，荐诸国王。王忻然下诏，有二三大夫言其怪状，恐惊圣体，王乃止。郎出告马，深为扼腕。居久之，与主人饮而醉，把剑起舞，以煤涂面作张飞。主人以为美，曰：“请君以张飞见宰相，厚禄不难致。”马曰：“游戏犹可，何能易面目图荣显？”主人强之，马乃诺。主人设筵，邀当路者，令马绘面以待。客至，呼马出见客。客讶曰：“异哉！何前媸而今妍也！”遂与共饮，甚欢。马婆娑歌“弋阳曲”，一座无不倾倒。明日交章荐马，王喜，召以旌节。既见，问中国治安之道，马委曲上陈，大蒙嘉叹，赐宴离宫。酒酣，王曰：“闻卿善雅乐，可使寡人得而闻之乎？”马即起舞，亦效白锦缠头，作靡靡之音。王大悦，即日拜下大夫。时与私宴，恩宠殊异。久而官僚知其面目之假，所至，辄见人耳语，不甚与款洽。马至是孤立，怡然不自安。遂上疏乞休致，不许；又告休沐，乃给三月假。
于是乘传载金宝，复归村。村人膝行以迎。马以金资分给旧所与交好者，欢声雷动。村人曰：“吾侪小人受大夫赐，明日赴海市，当求珍玩以报”，问：“海市何地？”曰：“海中市，四海鲛人，集货珠宝。四方十二国，均来贸易。中多神人游戏。云霞障天，波涛间作。贵人自重，不敢犯险阻，皆以金帛付我辈代购异珍。今其期不远矣。”问所自知，曰：“每见海上朱鸟往来，七日即市。”马问行期，欲同游瞩，村人劝使自贵。马曰：“我顾沧海客，何畏风涛？”未几，果有踵门寄资者，遂与装资入船。船容数十人，平底高栏。十人摇橹，激水如箭。凡三日，遥见水云幌漾之中，楼阁层叠，贸迁之舟，纷集如蚁。少时抵城下，视墙上砖皆长与人等，敌楼高接云汉。维舟而入，见市上所陈，奇珍异宝，光明射目，多人世所无。
一少年乘骏马来，市人尽奔避，云是“东洋三世子。”世子过，目生曰：“此非异域人。”即有前马者来诘乡籍。生揖道左，具展邦族。世子喜曰：“既蒙辱临，缘分不浅！”于是授生骑，请与连辔。乃出西城，方至岛岸，所骑嘶跃入水。生大骇失声。则见海水中分，屹如壁立。俄睹宫殿，玳瑁为梁，鲂鳞作瓦，四壁晶明，鉴影炫目。下马揖入。仰视龙君在上，世子启奏：“臣游市廛，得中华贤士，引见大王。”生前拜舞。龙君乃言：“先生文学士，必能衙官屈、宋。欲烦椽笔赋‘海市’，幸无吝珠玉。”生稽首受命。授以水晶之砚，龙鬣之毫，纸光似雪，墨气如兰。生立成千余言，献殿上。龙君击节曰：“先生雄才，有光水国矣！”遂集诸龙族，宴集采霞宫。酒炙数行，龙君执爵向客曰：“寡人所怜女，未有良匹，愿累先生。先生倘有意乎？”生离席愧荷，唯唯而已。龙君顾左右语。无何，宫女数人扶女郎出，佩环声动，鼓吹暴作，拜竟睨之，实仙人也。女拜已而去。少时酒罢，双鬟挑画灯，导生入副宫，女浓妆坐伺。珊瑚之床饰以八宝，帐外流苏缀明珠如斗大，衾褥皆香软。天方曙，雏女妖鬟，奔入满侧。生起，趋出朝谢。拜为驸马都尉。以其赋驰传诸海。诸海龙君，皆专员来贺，争折简招驸马饮。生衣绣裳，坐青虬，呵殿而出。武士数十骑，背雕弧，荷白棓，晃耀填拥。马上弹筝，车中奏玉。三日间，遍历诸海。由是“龙媒”之名，噪于四海。宫中有玉树一株，围可合抱，本莹澈如白琉璃，中有心淡黄色，稍细于臂，叶类碧玉，厚一钱许，细碎有浓阴。常与女啸咏其下。花开满树，状类薝葡。每一瓣落，锵然作响。拾视之，如赤瑙雕镂，光明可爱。时有异鸟来鸣，毛金碧色，尾长于身，声等哀玉，恻人肺腑。生闻之，辄念故土。因谓女曰：“亡出三年，恩慈间阻，每一念及，涕膺汗背。卿能从我归乎？”女曰：“仙尘路隔，不能相依。妾亦不忍以鱼水之爱，夺膝下之欢。容徐谋之。”生闻之，涕不自禁。女亦叹曰：“此势之不能两全者也！”明日，生自外归。龙王曰：“闻都尉有故土之思，诘旦趣装，可乎？”生谢曰：“逆旅孤臣，过蒙优宠，衔报之思，结于肺腑。容暂归省，当图复聚耳。”入暮，女置酒话别。生订后会，女曰：“情缘尽矣。”生大悲，女曰：“归养双亲，见君之孝，人生聚散，百年犹旦暮耳，何用作儿女哀泣？此后妾为君贞，君为妾义，两地同心，即伉俪也，何必旦夕相守，乃谓之偕老乎？若渝此盟，婚姻不吉。倘虑中馈乏人，纳婢可耳。更有一事相嘱：自奉衣裳，似有佳朕，烦君命名。”生曰：“其女耶可名龙宫，男耶可名福海。”女乞一物为信，生在罗刹国所得赤玉莲花一对，出以授女。女曰：“三年后四月八日，君当泛舟南岛，还君体胤。”女以鱼革为囊，实以珠宝，授生曰：“珍藏之，数世吃着不尽也。”天微明，王设祖帐，馈遗甚丰。生拜别出宫，女乘白羊车。送诸海涘。生上岸下马，女致声珍重，回车便去，少顷便远，海水复合，不可复见。生乃归。
自浮海去，家人无不谓其已死；及至家人皆诧异。幸翁媪无恙，独妻已去帷。乃悟龙女“守义”之言，盖已先知也。父欲为生再婚，生不可，纳婢焉。谨志三年之期，泛舟岛中。见两儿坐在水面，拍流嬉笑，不动亦不沉。近引之，儿哑然捉生臂，跃入怀中。其一大啼，似嗔生之不援己者。亦引上之。细审之，一男一女，貌皆俊秀。额上花冠缀玉，则赤莲在焉。背有锦囊，拆视，得书云：“翁姑俱无恙。忽忽三年，红尘永隔；盈盈一水，青鸟难通，结想为梦，引领成劳。茫茫蓝蔚，有恨如何也！顾念奔月姮娥，且虚桂府；投梭织女，犹怅银河。我何人斯，而能永好？兴思及此，辄复破涕为笑。别后两月，竟得孪生。今已啁啾怀抱，颇解言笑；觅枣抓梨，不母可活。敬以还君。所贻赤玉莲花，饰冠作信。膝头抱儿时，犹妾在左右也。闻君克践旧盟，意愿斯慰。妾此生不二，之死靡他。奁中珍物，不蓄兰膏；镜里新妆，久辞粉黛。君似征人，妾作荡妇，即置而不御，亦何得谓非琴瑟哉？独计翁姑已得抱孙，曾未一觌新妇，揆之情理，亦属缺然。岁后阿姑窀穸，当往临穴，一尽妇职。过此以往，则‘龙宫’无恙，不少把握之期；‘福海’长生，或有往还之路。伏惟珍重，不尽欲言。”生反覆省书揽涕。两儿抱颈曰：“归休乎！”生益恸抚之，曰：“儿知家在何许？”儿啼，呕哑言归。生视海水茫茫，极天无际，雾鬟人渺，烟波路穷。抱儿返棹，怅然遂归。
生知母寿不永，周身物悉为预具，墓中植松槚百余。逾岁，媪果亡。灵舆至殡宫，有女子缞绖临穴。众惊顾，忽而风激雷轰，继以急雨，转瞬已失所在。松柏新植多枯，至是皆活。福海稍长，辄思其母，忽自投入海，数日始还。龙宫以女子不得往，时掩户泣。一日昼暝，龙女急入，止之曰：“儿自成家，哭泣何为？”乃赐八尺珊瑚一株，龙脑香一帖，明珠百粒，八宝嵌金合一双，为嫁资。生闻之突入，执手啜泣。俄顷，迅雷破屋，女已无矣。
异史氏曰：“花面逢迎，世情如鬼。嗜痂之癖，举世一辙。‘小惭小好，大惭大好’。若公然带须眉以游都市，其不骇而走者盖几希矣！彼陵阳痴子，将抱连城玉向何处哭也？呜呼！显荣富贵，当于蜃楼海市中求之耳！”
"""