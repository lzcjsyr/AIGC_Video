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
    raise ValueError("Missing required Azure credentials in .env file.")

################################################
summarize_story_system_prompt = """
### Task ###
Summarize long novels into shorter versions (2000 to 3000 words), ensuring that the summary retains the key plot points, character development, main themes, and narrative flow. 
The summarized version should be suitable for an audio format, conveying the essence of the original story.

### Context ###
The GPT specializes in creating concise novel summaries with a focus on storytelling for audio preparation. 
Summaries should maintain the emotional depth, character interactions, and primary themes, while omitting unnecessary details and side plots. 
The goal is to craft a condensed version that allows listeners to experience the core of the story without losing its impact.

### Tone ###
Engaging, conversational, and suitable for oral narration. 
The tone should be friendly and easy to follow, helping listeners feel immersed in the storytelling experience. 
Avoid overly formal or academic language, aiming for clarity and simplicity while respecting the depth of the original work.

### Format ###
- Length: 2000 to 3000 words.
- Preserve dialogue between characters to maintain personality and relationships.
- Use natural transitions between events.
- Exclude extraneous details, focusing only on plot and characters that are crucial to the story.
- Output must be in JSON format with the following structure (only output the JSON object, the first and last characters must be "{", "}"):
  {
    "title": "Story Title",
    "summary": "The summarized story content",
    "word_count": 0,
    "main_themes": ["Theme 1", "Theme 2", ...],
    "key_characters": [
      {
        "name": "Character Name",
        "description": "Brief character description"
      },
      ...
    ]
  }
"""

plot_splitter_system_prompt = """
#####
Task Type:
Analyze a story set in ancient China, identify the main characters, split the story into key plot points, and generate corresponding image prompts. 
Provide the output in JSON format with a list of the main characters and descriptions, followed by plot segmentation with image prompts that include detailed descriptions of the characters appearing in each scene.

#####
Instructions:
1. Analyze the story and generate a "characters list" with "gender, age, hairstyle, body size, key personalities" in the first response. 
2. Break the story into logical plot points (default:5) and provide detailed descriptions of each scene. 
3. For each plot, include an image generation prompt with these sections: Context of the plot, Image style, Characteristics of the times, Negative list, Character description (must refer to "characters list")
4. Ensure all images reflect the ancient Chinese setting, with photo realistic quality, fine details, and consistent characters throughout the story.
5. Generate images in landscape (horizontal) format.

#####
Output Format:
The output should be a JSON object with the following structure:
{
  "characters": [
    {
      "name": "Character Name",
      "gender": "Male/Female",
      "age": "Age description",
      "hairstyle": "Hairstyle description",
      "body_size": "Body size description",
      "key_personalities": ["Trait 1", "Trait 2", ...]
    },
    ...
  ],
  "plots": [
    {
      "num_plot": "Number of the plot",
      "plot_title": "Plot Title",
      "plot_description": "Plot description",
      "image_info": {
        "context": "Context of the plot",
        "image_style": "Image style description",
        "characteristics_of_times": "Historical details",
        "negative_list": ["Item 1 to avoid", "Item 2 to avoid", ...],
        "character_descriptions": [
          {
            "name": "Character Name",
            "gender": "Male/Female",
            "age": "Age description",
            "hairstyle": "Hairstyle description",
            "body_size": "Body size description",
            "key_personalities": ["Trait 1", "Trait 2", ...]
            "description": "Character description in this scene"
          },
          ...
        ]
      }
    },
    ...
  ]
}

#####
Positive actions:
1. Ensure consistent character descriptions across all images, including common descriptions for recurring characters in different plots, under "Character Description."
2. Maintain photorealism, fine details, and historical accuracy, with handsome men and beautiful women in traditional Chinese clothing.
3. Explicitly specify the ancient Chinese setting in each image prompt.

#####
Negative Actions:
1. No modern elements or technology.
2. Avoid inconsistencies in character design or emotional tone across scenes.
3. Do not introduce abstract or exaggerated artistic elements unless requested.
"""

generate_image_system_prompt = """
Generate single-scene prompts with these elements:

Image Style: Photorealistic, high-detail, epic composition, vivid colors, elegant features.
Characters: Specify age, gender, body type, hairstyle, and traditional Chinese attire.
Setting: Ancient China (exact period), authentic architecture, props, and landscapes.
Mood: Use dramatic lighting and atmosphere to enhance the scene's emotion.

Avoid: Modern elements, abstract styles, text overlays.
Output: Provide only the generated prompt, no explanations.
"""

story = """
Title: THE LO-CH‘A COUNTRY AND THE SEA-MARKET
Once upon a time there was a young man, named Ma Chün, who was also known as Lung-mei. He was the son of a trader, and a youth of surpassing beauty. His manners were courteous, and he loved nothing better than singing and playing. He used to associate with actors, and with an embroidered handkerchief round his head the effect was that of a beautiful woman. Hence he acquired the sobriquet of the Beauty. At fourteen years of age he graduated and began to make a name for himself; but his father, who was growing old and wished to retire from business, said to him, “My boy, book-learning will never fill your belly or put a coat on your back; you had much better stick to the old thing.” Accordingly, Ma from that time occupied himself with scales and weights, with principle and interest, and such matters.
He made a voyage across the sea, and was carried away by a typhoon. After being tossed about for many days and nights he arrived at a country where the people were hideously ugly. When these people saw Ma they thought he was a devil and all ran screeching away. Ma was somewhat alarmed at this, but finding that it was they who were frightened at him, he quickly turned their fear to his own advantage. If he came across people eating and drinking he would rush upon them, and when they fled away for fear, he would regale himself upon what they had left. By-and-by he went to a village among the hills, and there the people had at any rate some facial resemblance to ordinary men. But they were all in rags and tatters like beggars. So Ma sat down to rest under a tree, and the villagers, not daring to come near him, contented themselves with looking at him from a distance. They soon found, however, that he did not want to eat them, and by degrees approached a little closer to him. Ma, smiling, began to talk; and although their language was different, yet he was able to make himself tolerably intelligible, and told them whence he had come. The villagers were much pleased, and spread the news that the stranger was not a man-eater. Nevertheless, the very ugliest of all would only take a look and be off again; they would not come near him. Those who did go up to him were not very much unlike his own countrymen, the Chinese. They brought him plenty of food and wine. Ma asked them what they were afraid of. They replied, “We had heard from our forefathers that 26,000 li to the west there is a country called China. We had heard that the people of that land were the most extraordinary in appearance you can possibly imagine. Hitherto it has been hearsay; we can now believe it.” He then asked them how it was they were so poor. They answered, “You see, in our country everything depends, not on literary talent, but on beauty. The most beautiful are made ministers of state; the next handsomest are made judges and magistrates; and the third class in looks are employed in the palace of the king. Thus these are enabled out of their pay to provide for their wives and families. But we, from our very birth, are regarded by our parents as inauspicious, and are left to perish, some of us being occasionally preserved by more humane parents to prevent the extinction of the family.” Ma asked the name of their country, and they told him it was Lo-ch‘a. Also that the capital city was some 30 li to the north. He begged them to take him there, and next day at cock-crow he started thitherwards in their company, arriving just about dawn. The walls of the city were made of black stone, as black as ink, and the city gate-houses were about 100 feet high. Red stones were used for tiles, and picking up a broken piece Ma found that it marked his finger-nail like vermilion. They arrived just when the Court was rising, and saw all the equipages of the officials. The village people pointed out one who they said was Prime Minister. His ears drooped forward in flaps; he had three nostrils, and his eye-lashes were just like bamboo screens hanging in front of his eyes. Then several came out on horseback, and they said these were the privy councillors. So they went on, telling him the rank of all the ugly uncouth fellows he saw. The lower they got down in the official scale the less hideous the officials were. By-and-by Ma went back, the people in the streets marvelling very much to see him, and tumbling helter-skelter one over another as if they had met a goblin. The villagers shouted out to re-assure them, and then they stood at a distance to look at him. When he got back, there was not a man, woman, or child in the whole nation but knew that there was a strange man at the village; and the gentry and officials became very desirous to see him. However, if he went to any of their houses the porter always slammed the door in his face, and the master, mistress, and family, in general, would only peep at, and speak to him through the cracks. Not a single one dared receive him face to face; but, finally, the village people, at a loss what to do, bethought themselves of a man who had been sent by a former king on official business among strange nations. “He,” said they, “having seen many kinds of men, will not be afraid of you.” So they went to his house, where they were received in a very friendly way. He seemed to be about eighty or ninety years of age; his eye-balls protruded, and his beard curled up like a hedge-hog. He said, “In my youth I was sent by the king among many nations, but I never went to China. I am now one hundred and twenty years of age, and that I should be permitted to see a native of your country is a fact which it will be my duty to report to the Throne. For ten years and more I have not been to Court, but have remained here in seclusion; yet I will now make an effort on your behalf.” Then followed a banquet, and when the wine had already circulated pretty freely, some dozen singing girls came in and sang and danced before them. The girls all wore white embroidered turbans, and long scarlet robes which trailed on the ground. The words they uttered were unintelligible, and the tunes they played perfectly hideous. The host, however, seemed to enjoy it very much, and said to Ma, “Have you music in China?” He replied that they had, and the old man asked for a specimen. Ma hummed him a tune, beating time on the table, with which he was very much pleased, declaring that his guest had the voice of a phœnix and the notes of a dragon, such as he had never heard before. The next day he presented a memorial to the Throne, and the king at once commanded Ma to appear before him. Several of the ministers, however, represented that his appearance was so hideous it might frighten His Majesty, and the king accordingly desisted from his intention. The old man returned and told Ma, being quite upset about it. They remained together some time until they had drunk themselves tipsy. Then Ma, seizing a sword, began to attitudinize, smearing his face all over with coal-dust. He acted the part of Chang Fei,at which his host was so delighted that he begged him to appear before the Prime Minister in the character of Chang Fei. Ma replied, “I don’t mind a little amateur acting, but how can I play the hypocrite for my own personal advantage?” On being pressed he consented, and the old man prepared a great feast, and asked some of the high officials to be present, telling Ma to paint himself as before. When the guests had arrived, Ma was brought out to see them; whereupon they all exclaimed, “Ai-yah! how is it he was so ugly before and is now so beautiful?” By-and-by, when they were all taking wine together, Ma began to sing them a most bewitching song, and they got so excited over it that next day they recommended him to the king. The king sent a special summons for him to appear, and asked him many questions about the government of China, to all of which Ma replied in detail, eliciting sighs of admiration from His Majesty. He was honoured with a banquet in the royal guest-pavilion, and when the king had made himself tipsy he said to him, “I hear you are a very skilful musician. Will you be good enough to let me hear you?” Ma then got up and began to attitudinize, singing a plaintive air like the girls with the turbans. The king was charmed, and at once made him a privy councillor, giving him a private banquet, and bestowing other marks of royal favour. As time went on his fellow-officials found out the secret of his painted face, and whenever he was among them they were always whispering together, besides which they avoided being near him as much as possible. Thus Ma was left to himself, and found his position anything but pleasant in consequence. So he memorialized the Throne, asking to be allowed to retire from office, but his request was refused. He then said his health was bad, and got three months’ sick leave, during which he packed up his valuables and went back to the village. The villagers on his arrival went down on their knees to him, and he distributed gold and jewels amongst his old friends. They were very glad to see him, and said, “Your kindness shall be repaid when we go to the sea-market; we will bring you some pearls and things.” Ma asked them where that was. They said it was at the bottom of the sea, where the mermaids kept their treasures, and that as many as twelve nations were accustomed to go thither to trade. Also that it was frequented by spirits, and that to get there it was necessary to pass through red vapours and great waves. “Dear Sir,” they said, “do not yourself risk this great danger, but let us take your money and purchase these rare pearls for you. The season is now at hand.” Ma asked them how they knew this. They said, “Whenever we see red birds flying backwards and forwards over the sea, we know that within seven days the market will open.” He asked when they were going to start, that he might accompany them; but they begged him not to think of doing so. He replied, “I am a sailor: how can I be afraid of wind and waves?” Very soon after , people came with merchandise to forward, and so Ma packed up and went on board the vessel that was going.
This vessel held some tens of people, was flat-bottomed with a railing all round, and, rowed by ten men, it cut through the water like an arrow. After a voyage of three days they saw afar off faint outlines of towers and minarets, and crowds of trading vessels. They soon arrived at the city, the walls of which were made of bricks as long as a man’s body, the tops of its buildings being lost in the Milky Way. Having made fast their boat they went in, and saw laid out in the market rare pearls and wondrous precious stones of dazzling beauty, such as are quite unknown amongst men. Then they saw a young man come forth riding upon a beautiful steed. The people of the market stood back to let him pass, saying he was the third son of the king; but when the Prince saw Ma, he exclaimed, “This is no foreigner,” and immediately an attendant drew near and asked his name and country. Ma made a bow, and standing at one side told his name and family. The prince smiled, and said, “For you to have honoured our country thus is no small piece of good luck.” He then gave him a horse and begged him to follow. They went out of the city gate and down to the sea-shore, whereupon their horses plunged into the water. Ma was terribly frightened and screamed out; but the sea opened dry before them and formed a wall of water on either side. In a little time they reached the king’s palace, the beams of which were made of tortoise-shell and the tiles of fishes’ scales. The four walls were of crystal, and dazzled the eye like mirrors. They got down off their horses and went in, and Ma was introduced to the king. The young prince said, “Sire, I have been to the market, and have got a gentleman from China.” Whereupon Ma made obeisance before the king, who addressed him as follows:—“Sir, from a talented scholar like yourself I venture to ask for a few stanzas upon our sea-market. Pray do not refuse.” Ma thereupon made a kot‘ow and undertook the king’s command. Using an ink-slab of crystal, a brush of dragon’s beard, paper as white as snow, and ink scented like the larkspur, Ma immediately threw off some thousand odd verses, which he laid at the feet of the king. When His Majesty saw them, he said, “Sir, your genius does honour to these marine nations of ours.” Then, summoning the members of the royal family, the king gave a great feast in the Coloured Cloud pavilion; and, when the wine had circulated freely, seizing a great goblet in his hand, the king rose and said before all the guests, “It is a thousand pities, Sir, that you are not married. What say you to entering the bonds of wedlock?” Ma rose blushing, and stammered out his thanks; upon which the king looking round spoke a few words to the attendants, and in a few moments in came a bevy of court ladies supporting the king’s daughter, whose ornaments went tinkle, tinkle, as she walked along. Immediately the nuptial drums and trumpets began to sound forth, and bride and bridegroom worshipped Heaven and Earth together. Stealing a glance Ma saw that the princess was endowed with a fairy-like loveliness. When the ceremony was over she retired, and by-and-by the wine-party broke up. Then came several beautifully-dressed waiting-maids, who with painted candles escorted Ma within. The bridal couch was made of coral adorned with eight kinds of precious stones, and the curtains were thickly hung with pearls as big as acorns. Next day at dawn a crowd of young slave-girls trooped into the room to offer their services; whereupon Ma got up and went off to Court to pay his respects to the king. He was then duly received as royal son-in-law and made an officer of state. The fame of his poetical talents spread far and wide, and the kings of the various seas sent officers to congratulate him, vying with each other in their invitations to him. Ma dressed himself in gorgeous clothes, and went forth riding on a superb steed, with a mounted body-guard all splendidly armed. There were musicians on horseback and musicians in chariots, and in three days he had visited every one of the marine kingdoms, making his name known in all directions. In the palace there was a jade tree, about as big round as a man could clasp. Its roots were as clear as glass, and up the middle ran, as it were, a stick of pale yellow. The branches were the size of one’s arm; the leaves like white jade, as thick as a copper cash. The foliage was dense, and beneath its shade the ladies of the palace were wont to sit and sing. The flowers which covered the tree resembled grapes, and if a single petal fell to the earth it made a ringing sound. Taking one up, it would be found to be exactly like carved cornelian, very bright and pretty to look at. From time to time a wonderful bird came and sang there. Its feathers were of a golden hue, and its tail as long as its body. Its notes were like the tinkling of jade, very plaintive and touching to listen to. When Ma heard this bird sing, it called up in him recollections of his old home, and accordingly he said to the princess, “I have now been away from my own country for three years, separated from my father and mother. Thinking of them my tears flow and the perspiration runs down my back. Can you return with me?” His wife replied, “The way of immortals is not that of men. I am unable to do what you ask, but I cannot allow the feelings of husband and wife to break the tie of parent and child. Let us devise some plan.” When Ma heard this he wept bitterly, and the princess sighed and said, “We cannot both stay or both go.” The next day the king said to him, “I hear that you are pining after your old home. Will to-morrow suit you for taking leave?” Ma thanked the king for his great kindness, which he declared he could never forget, and promised to return very shortly. That evening the princess and Ma talked over their wine of their approaching separation. Ma said they would soon meet again; but his wife averred that their married life was at an end. Then he wept afresh, but the princess said, “Like a filial son you are going home to your parents. In the meetings and separations of this life, a hundred years seem but a single day; why, then, should we give way to tears like children? I will be true to you; do you be faithful to me; and then, though separated, we shall be united in spirit, a happy pair. Is it necessary to live side by side in order to grow old together? If you break our contract your next marriage will not be a propitious one; but if loneliness overtakes you then choose a concubine. There is one point more of which I would speak, with reference to our married life. I am about to become a mother, and I pray you give me a name for your child.” To this Ma replied, “If a girl I would have her called Lung-kung; if a boy, then name him Fu-hai.” The princess asked for some token of remembrance, and Ma gave her a pair of jade lilies that he had got during his stay in the marine kingdom. She added, “On the 8th of the 4th moon, three years hence, when you once more steer your course for this country, I will give you up your child.” She next packed a leather bag full of jewels and handed it to Ma, saying, “Take care of this; it will be a provision for many generations.” When the day began to break a splendid farewell feast was given him by the king, and Ma bade them all adieu. The princess, in a car drawn by snow-white sheep, escorted him to the boundary of the marine kingdom, where he dismounted and stepped ashore. “Farewell!” cried the princess, as her returning car bore her rapidly away, and the sea, closing over her, snatched her from her husband’s sight. Ma returned to his home across the ocean. Some had thought him long since dead and gone; all marvelled at his story. Happily his father and mother were yet alive, though his former wife had married another man; and so he understood why the princess had pledged him to constancy, for she already knew that this had taken place. His father wished him to take another wife, but he would not. He only took a concubine. Then, after the three years had passed away, he started across the sea on his return journey, when lo! he beheld, riding on the wave-crests and splashing about the water in playing, two young children. On going near, one of them seized hold of him and sprung into his arms; upon which the elder cried until he, too, was taken up. They were a boy and girl, both very lovely, and wearing embroidered caps adorned with jade lilies. On the back of one of them was a worked case, in which Ma found the following letter:—
“I presume my father and mother-in-law are well. Three years have passed away and destiny still keeps us apart. Across the great ocean, the letter-bird would find no path. I have been with you in my dreams until I am quite worn out. Does the blue sky look down upon any grief like mine? Yet Ch‘ang-ngo lives solitary in the moon, and Chih Nü laments that she cannot cross the Silver River. Who am I that I should expect happiness to be mine? Truly this thought turns my tears into joy. Two months after your departure I had twins, who can already prattle away in the language of childhood, at one moment snatching a date, at another a pear. Had they no mother they would still live. These I now send to you, with the jade lilies you gave me in their hats, in token of the sender. When you take them upon your knee, think that I am standing by your side. I know that you have kept your promise to me, and I am happy. I shall take no second husband, even unto death. All thoughts of dress and finery are gone from me; my looking-glass sees no new fashions; my face has long been unpowdered, my eyebrows unblacked. You are my Ulysses, I am your Penelope; though not actually leading a married life, how can it be said that we are not husband and wife. Your father and mother will take their grandchildren upon their knees, though they have never set eyes upon the bride. Alas! there is something wrong in this. Next year your mother will enter upon the long night. I shall be there by the side of the grave as is becoming in her daughter-in-law. From this time forth our daughter will be well; later on she will be able to grasp her mother’s hand. Our boy, when he grows up, may possibly be able to come to and fro. Adieu, dear husband, adieu, though I am leaving much unsaid.” Ma read the letter over and over again, his tears flowing all the time. His two children clung round his neck, and begged him to take them home. “Ah, my children,” said he, “where is your home?” Then they all wept bitterly, and Ma, looking at the great ocean stretching away to meet the sky, lovely and pathless, embraced his children, and proceeded sorrowfully to return. Knowing, too, that his mother could not last long, he prepared everything necessary for the ceremony of interment, and planted a hundred young pine-trees at her grave. The following year the old lady did die, and her coffin was borne to its last resting-place, when lo! there was the princess standing by the side of the grave. The lookers-on were much alarmed, but in a moment there was a flash of lightning, followed by a clap of thunder and a squall of rain, and she was gone. It was then noticed that many of the young pine-trees which had died were one and all brought to life. Subsequently, Fu-hai went in search of the mother for whom he pined so much, and after some days’ absence returned. Lung-kung, being a girl, could not accompany him, but she mourned much in secret. One dark day her mother entered and bid her dry her eyes, saying, “My child, you must get married. Why these tears?” She then gave her a coral tree eight feet in height, some Baroos camphor, one hundred valuable pearls, and two boxes inlaid with gold and precious stones, as her dowry. Ma, having found out she was there, rushed in and seizing her hand, began to weep for joy, when suddenly a violent peal of thunder rented the building, and the princess vanished.
"""