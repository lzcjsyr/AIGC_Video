################################################
story_parser_system_prompt = """
### Task Introduction ###
As a story parser, convert lengthy narratives into a structured JSON format following specific guidelines for content retention, analysis, and output formatting.

### Guidelines ###
1. Character Analysis
   - Identify key characters
   - Include: gender, age, hairstyle, body size, key traits
   - Infer age, hairstyle, and body size logically. All fields must be filled!!!

2. Plot Segmentation
   - Default: 5 key plot points
   - Ensure smooth, attractive transitions
   - Treat each plot as an episode
   - End with engaging hooks
   - The character name must refer to the name in "key_characters"!!!

3. Content Focus
   - Retain key story elements
   - Emphasize emotional depth and significant interactions
   - Respect the original work's complexity
   - Extract places, Times and Mood of the story

4. Narrative Style
   - Engaging and conversational
   - Suitable for oral narration
   - Avoid overly formal or academic language

5. Output Format
   - Strictly adhere to specified JSON structure
   - Follow all description requirements within the JSON

### Output Format ###
Output must be in JSON format with the following structure (only output the JSON object, the first and last characters must be "{", "}"):
{
  "title": "Story Title",
  "story_elements": ["Places", "Times", "Mood"]
  "key_characters": [
    {
      "name": "Character Name",
      "gender": "Male/Female",
      "age": "Age description (Infer logically. All fields must be filled!!!)",
      "hairstyle": "Hairstyle description (Infer logically. All fields must be filled!!!)",
      "body_size": "Body size description (Infer logically. All fields must be filled!!!)",
      "description": ["Trait 1", "Trait 2", "Trait 3"]
    },
    "..."
  ],
  "Segmentation": [
    {
      "plot": "Engaging and conversational; smooth, attractive transitions; between 350 to 450 words",
      "plot_theme": ["Theme 1", "Theme 2", "Theme 3"]
      "characters_name": ["name 1", ... (Must refer to the name in "key_characters"!!!)]
    },
    "..."
  ]
}
"""

generate_image_system_prompt = """
Generate single-scene prompt with these guidelines:

##### Images Elements #####
1. Characters key information (EXTREMELY IMPORTANT): Specify age, gender, body type, hairstyle
2. Characters features: Vibrant colors, Charming, Celebrity-like, Dynamic pose
3. Artistic Style: photograph (Makoto Shinkai)
4. Image features: photograph, high-detail 32k UHD, epic, elegant, romantic
5. Background Setting: Ancient China
6. Atmosphere: cinematic lighting and ambiance

##### Don't #####
1. Negative list: modern element, western culture, technology
2. No extract words other than the prompt. 
"""

story = """
THE HERD BOY AND THE WEAVING MAIDEN
THE Herd Boy was the child of poor people. When he was twelve years old, he took service with a farmer to herd his cow. After a few years the cow had grown large and fat, and her hair shone like yellow gold. She must have been a cow of the gods.
One day while he had her out at pasture in the mountains, she suddenly began to speak to the Herd Boy in a human voice, as follows: “This is the Seventh Day. Now the White Jade Ruler has nine daughters, who bathe this day in the Sea of Heaven. The seventh daughter is beautiful and wise beyond all measure. She spins the cloud-silk for the King and Queen of Heaven, and presides over the weaving which maidens do on earth. It is for this reason she is called the Weaving Maiden. And if you go and take away her clothes while she bathes, you may become her husband and gain immortality.”
“But she is up in Heaven,” said the Herd Boy, “and how can I get there?”
“I will carry you there,” answered the yellow cow.
So the Herd Boy climbed on the cow’s back. In a moment clouds began to stream out of her hoofs, and she rose into the air. About his ears there was whistling like the sound of the wind, and they flew along as swiftly as lightning. Suddenly the cow stopped.
“Now we are here,” said she.
Then round about him the Herd Boy saw forests of chrysophrase and trees of jade. The grass was of jasper and the flowers of coral. In the midst of all this splendor lay a great, four-square sea, covering some five-hundred acres. Its green waves rose and fell, and fishes with golden scales were swimming about in it. In addition there were countless magic birds who winged above it and sang. Even in the distance, the Herd Boy could see the nine maidens in the water. They had all laid down their clothes on the shore.
“Take the red clothes, quickly,” said the cow, “and hide away with them in the forest, and though she ask you for them never so sweetly do not give them back to her until she has promised to become your wife.”
Then the Herd Boy hastily got down from the cow’s back, seized the red clothes and ran away. At the same moment, the nine maidens noticed him and were very frightened.
“O youth, whence do you come, that you dare to take our clothes?” they cried. “Put them down again quickly!”
But the Herd Boy did not let what they said trouble him, but crouched down behind one of the jade trees. Then eight of the maidens hastily came ashore and drew on their clothes.
“Our seventh sister,” said they, “whom Heaven has destined to be yours, has come to you. We will leave her alone with you.”
The Weaving Maiden was still crouching in the water.
But the Herd Boy stood before her and laughed.
“If you will promise to be my wife,” said he, “then I will give you your clothes.”
But this did not suit the Weaving Maiden.
“I am a daughter of the Ruler of the Gods,” said she, “and may not marry without his command. Give back my clothes to me quickly, or else my father will punish you!”
Then the yellow cow said: “You have been destined for each other by fate, and I will be glad to arrange your marriage, and your father, the Ruler of the Gods, will make no objection. Of that I am sure.”
The Weaving Maiden replied: “You are an unreasoning animal! How could you arrange our marriage?”
The cow said: “Do you see that old willow-tree there on the shore? Just give it a trial and ask it. If the willow tree speaks, then Heaven wishes your union.”
And the Weaving Maiden asked the willow.
The willow replied in a human voice:
“This is the Seventh day,The Herd Boy his court to the Weaver doth pay!”
and the Weaving Maiden was satisfied with the verdict. The Herd Boy laid down her clothes, and went on ahead. The Weaving Maiden drew them on and followed him. And thus they became men and wives.
But after seven days she took leave of him.
“The Ruler of Heaven has ordered me to look after my weaving,” said she. “If I delay too long I fear that he will punish me. Yet, although we have to part now, we will meet again in spite of it.”
When she had said these words she really went away. The Herd Boy ran after her. But when he was quite near, she took one of the long needles from her hair and drew a line with it right across the sky, and this line turned into the Silver River. And thus they now stand, separated by the river, and watch for one another.
And since that time they meet once every year, on the eve of the Seventh Day. When that time comes, then all the crows in the world of men come flying and form a bridge over which the Weaving Maiden crosses the Silver River. And on that day you will not see a single crow in the trees, from morning to night, no doubt because of the reason I have mentioned. And besides, a fine rain often falls on the evening of the Seventh Day. Then the women and old grandmothers say to one another: “Those are the tears which the Herd Boy and the Weaving Maiden shed at parting!” And for this reason, the Seventh Day is a rain festival.
To the west of the Silver River is the constellation of the Weaving Maiden, consisting of three stars. And directly in front of it are three other stars in the form of a triangle. It is said that once the Herd Boy was angry because the Weaving Maiden had not wished to cross the Silver River, and had thrown his yoke at her, which fell down just in front of her feet. East of the Silver River is the Herd Boy’s constellation, consisting of six stars. To one side of it are countless little stars which form a constellation pointed at both ends and somewhat broader in the middle. It is said that the Weaving Maiden in turn threw her spindle at the Herd Boy; but that she did not hit him, the spindle falling down to one side of him.
Note: “The Herd Boy and the Weaving Maiden” is retold after an oral source. The Herd Boy is a constellation in Aquila, the Weaving Maiden one in Lyra. The Silver River which separates them is the Milky Way. The Seventh Day of the seventh month is the festival of their reunion. The Ruler of the Heavens has nine daughters in all, who dwell in the nine heavens. The oldest married Li Dsing ; the second is the mother of Yang Oerlang ; the third is the mother of the planet Jupiter ; and the fourth dwelt with a pious and industrious scholar, by name of Dung Yung, whom she aided to win riches and honor. The seventh is the Spinner, and the ninth had to dwell on earth as a slave because of some transgression of which she had been guilty. Of the fifth, the sixth and the eighth daughters nothing further is known."""