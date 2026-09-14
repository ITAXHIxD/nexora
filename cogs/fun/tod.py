"""
cogs/fun/tod.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Truth or Dare Engine
Supports Solo and PvP challenges, multiple rating tiers (PG / Teen / Spicy),
and forfeit penalty tracking with interactive buttons.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

# ── Truth & Dare Prompt Database ───────────────────────────────────────────────

TRUTHS = {
    "pg": [
        "What is the most embarrassing thing your parents caught you doing?",
        "If you could trade lives with anyone in this server for 24 hours, who would it be?",
        "What is the weirdest food combination you actually enjoy eating?",
        "Have you ever pretended to be sick to avoid hanging out with friends?",
        "What is the dumbest argument you have ever had with someone?",
        "What is your biggest guilty pleasure song or movie?",
        "What is one habit you have that you would never admit in public?",
        "If you had to delete every app on your phone except three, which three stay?",
        "What is the most childish thing you still do as an almost-adult?",
        "Have you ever laughed so hard that something came out of your nose?",
        "What cartoon character were you irrationally terrified of as a kid?",
        "What is the most ridiculous excuse you ever gave a teacher or boss for being late?",
        "Have you ever accidentally waved back at someone who wasn't waving at you?",
        "What is the single worst meal you have ever cooked or prepared yourself?",
        "If you were an animal, what species would match your exact personality?",
        "Have you ever tripped and fallen in public and pretended to tie your shoe to play it off?",
        "What is something you believed for way too long before finding out it wasn't true?",
        "If you had to listen to one song on repeat for 48 hours, which one could you survive?",
        "What is the weirdest nickname anyone has ever given you?",
        "Have you ever talked to yourself in the mirror and lost the argument?",
        "What is the funniest thing you believed as a child about how the world works?",
        "If you could have any useless superpower, what would you choose?",
        "What is your most irrational fear that makes zero logical sense?",
        "Have you ever eaten something that dropped on the floor past the 5-second rule?",
        "What is the longest you have gone without taking a shower?",
        "If you were forced to live inside a video game universe forever, which game would you pick?",
        "What is a popular movie or TV show that everyone loves but you secretly despise?",
        "Have you ever practiced an argument or speech in the shower with full dramatic hand gestures?",
        "What is the weirdest dream you remember having recently?",
        "If your pet could talk for 10 minutes, what is the first thing they would expose you for?",
        "What is the most useless talent or party trick you possess?",
        "Have you ever walked into a room and completely forgotten why you went there?",
        "What is your go-to comfort food when you are feeling completely down?",
        "If you could erase one embarrassing memory from your brain forever, what would it be?",
        "What is the weirdest thing you have ever collected or hoarded?",
        "Have you ever cried during an animated movie? If so, which one broke you?",
        "What is the most bizarre thing you have ever witnessed a stranger do in public?",
        "If you had to wear one Halloween costume every day for a whole month, what would it be?",
        "What is the silliest thing you have ever cried over?",
        "Have you ever sung at the top of your lungs in the car only to notice someone staring at a red light?",
        "What is your most controversial opinion about pizza toppings?",
        "If you won a million dollars tomorrow, what is the first completely unnecessary thing you would buy?",
        "What is the worst fashion trend you proudly participated in back in the day?",
        "Have you ever stayed awake until sunrise doing absolutely nothing productive?",
        "If you had a warning label tattooed on you, what would it say?",
        "What is your absolute least favorite chore to do around the house?",
        "Have you ever faked knowing about a band or topic just to fit into a conversation?",
        "If you were a flavor of ice cream, what flavor would you be and why?",
        "What is the most awkward handshake or high-five moment you have ever suffered through?",
        "Have you ever looked for something for 10 minutes only to realize it was in your hand?",
        "What is the funniest WiFi network name you have ever seen?",
        "If you could only eat food of one color for a week, which color are you choosing?",
        "What is your absolute favorite childhood memory that still brings a smile to your face?",
        "Have you ever accidentally liked a post from 3 years ago while stalking someone?",
        "What board game ruins friendships fastest in your experience?",
        "If your life was turned into a sitcom, what would the title be?",
        "What is the most ridiculous rumor someone ever spread about you?",
        "Have you ever tried to unlock your front door with your car remote?",
        "If you had to give a 30-minute TED talk right this second with zero prep, what topic are you picking?",
        "What is the weirdest superstition you secretly follow?",
        "Have you ever laughed at a completely inappropriate moment and had to cough to cover it up?",
        "What is your spirit vegetable and why?",
        "If you were arrested with zero context, what would your friends assume you did?",
        "What is the best piece of advice you have ever received that you actually followed?",
        "Have you ever replied to an email or text with 'sorry, just seeing this' when you saw it 3 weeks ago?",
    ],
    "teen": [
        "What is the biggest lie you have told on Discord or social media?",
        "Who in this server would you trust the least with your unlocked phone?",
        "What is the cringiest message you ever sent to someone you had a crush on?",
        "Have you ever ghosted someone because you were simply too lazy to reply?",
        "What is something you searched up on Google that you immediately cleared from your history?",
        "If you had to date someone currently in this voice or text channel, who would it be?",
        "What is the biggest secret you kept from your best friend?",
        "Have you ever stalked someone's profile for more than 30 minutes straight?",
        "What is the worst haircut or fashion disaster you have ever committed?",
        "Have you ever blamed a pet or sibling for something that was 100% your fault?",
        "Who was your very first fictional character crush?",
        "What is the petty reason you stopped talking to someone?",
        "What is the highest daily screen time you have ever clocked on your phone?",
        "Have you ever muted a group chat because you couldn't stand one specific person?",
        "What is something you pretend to dislike just because it's popular to hate on it?",
        "Have you ever sent a screenshot of a chat to the exact person the screenshot was about?",
        "What is the most desperate thing you have done for someone's attention?",
        "If your camera roll was projected onto a big screen right now, how cooked are you on a scale of 1-10?",
        "What is the cringiest username or gamertag you ever unironically used?",
        "Have you ever faked having bad WiFi or internet connection just to leave a voice call?",
        "Who in this server has the most chaotic aura and keeps you on edge?",
        "Have you ever pretended to fall asleep while texting someone just to end the conversation?",
        "What is the biggest rumor you ever accidentally started?",
        "If you had to delete either Discord, TikTok, or Instagram forever, which one goes first?",
        "Have you ever stalked an ex or former friend from a burner or alt account?",
        "What is the weirdest thing you have done when you were home completely alone?",
        "Have you ever lied about your age, location, or hobbies on the internet?",
        "Who was the last person you looked up on social media and why?",
        "What is the most dramatic meltdown you had over a video game or minor inconvenience?",
        "Have you ever talked trash about someone in this server and then acted like best friends later?",
        "What is your biggest ick in people that immediately turns you away?",
        "Have you ever re-read your own text messages repeatedly after sending them?",
        "What is the longest time you spent drafting a single text or DM before sending it?",
        "Have you ever stalked someone's Spotify listening activity or liked playlists?",
        "What is something embarrassing that you do when nobody is around to judge you?",
        "If you could read the DMs of any one person in this server for 5 minutes, whose DMs are you opening?",
        "Have you ever unfriended or blocked someone without giving them any explanation?",
        "What is the most awkward interaction you have had with a crush in real life?",
        "Have you ever lied on your resume or school application about an achievement?",
        "What is the dumbest thing you have bought with your own money that you immediately regretted?",
        "If someone offered you $5,000 to never speak to your best friend again, would you take it?",
        "What is the biggest secret you are currently keeping from your parents?",
        "Have you ever pretended to be busy when you were literally lying in bed staring at the ceiling?",
        "What is the cringiest trend or TikTok dance you secretly tried in your room?",
        "Who in this server would survive the longest in a zombie apocalypse, and who dies first?",
        "Have you ever taken credit for someone else's joke and everyone laughed?",
        "What is your most embarrassing playlist title on your music app?",
        "Have you ever accidentally sent a voice note that had background sounds you didn't want heard?",
        "What is the most dramatic text message you have ever sent in all caps?",
        "Have you ever left a server or group chat just to see if anyone would reach out and ask why you left?",
        "What is the weirdest photo currently sitting in your 'Hidden' album?",
        "If you could unmeet one person you know in real life, who would it be?",
        "Have you ever pretended to laugh at a meme you didn't understand just to avoid feeling left out?",
        "What is the most awkward thing your parents have walked in on you doing?",
        "Have you ever had an online beef or argument that you took way too seriously?",
        "Who in this server do you think has the best music taste, and who has the worst?",
        "What is a lie you told that you still have to maintain to this day because it went too far?",
        "Have you ever muted yourself in a voice call just to scream at your monitor?",
        "What is the cringiest thing you ever posted on your story or status?",
        "Have you ever stayed up until 4 AM texting someone and regretted it the next morning?",
        "What is a habit you picked up from a fictional character and never stopped doing?",
        "Who in this server would you trust the most to hide a body with you?",
        "Have you ever screenshot a text just to dissect the wording with your friends?",
        "What is the pettiest thing you have ever done to get revenge on someone?",
        "If your Discord search history was read aloud right now, what would surprise people the most?",
    ],
    "spicy": [
        "What is your biggest red flag that you actively try to hide?",
        "Who in this server do you secretly find the most attractive?",
        "What is the most scandalous DM currently sitting in your message history?",
        "Have you ever flirted with someone just to get something you wanted?",
        "What is the wildest thing on your bucket list that you would never tell your family?",
        "Have you ever had a crush on someone who was completely off-limits?",
        "What is the most rebellious thing you have done without getting caught?",
        "If you were forced to confess your deepest secret to someone in this server right now, who would you choose?",
        "What is a lie you told that spiraled completely out of control?",
        "Have you ever sent a risky text and immediately thrown your phone across the room in panic?",
        "What is your biggest toxic trait in relationships or friendships?",
        "Have you ever had feelings for two people at the exact same time?",
        "What is the most flattering compliment you have ever received that you still think about?",
        "If you had to kiss someone currently in this voice or text channel, who would you pick?",
        "Have you ever kept talking to an ex or crush long after you knew it was a bad idea?",
        "What is the craziest thing you have ever done purely out of jealousy?",
        "Have you ever accidentally liked a post while stalking someone's romantic partner?",
        "What is the fastest you have ever caught feelings for someone?",
        "Have you ever lied about your dating experience to seem more mature or experienced?",
        "What is your biggest guilty pleasure when it comes to romance or drama?",
        "If someone went through your saved photos or bookmarked tweets, what would they find?",
        "Have you ever given someone mixed signals on purpose because you enjoyed the chase?",
        "What is the most embarrassing date or hangout you have ever been on?",
        "Have you ever had a dream about someone in this server that you never told them about?",
        "What is a dealbreaker in romance that others think is completely unreasonable?",
        "Have you ever secretly checked someone's horoscope or birth chart to see if you were compatible?",
        "What is the boldest pickup line or flirty message you have ever used that actually worked?",
        "If you had to pick one person in this server to be stranded on a deserted island with, who is it?",
        "Have you ever stayed in a situationship way longer than you should have?",
        "What is the most dramatic confrontation you have ever had with someone?",
        "Have you ever stalked someone's following list to see who they recently added?",
        "What is something you find extremely attractive in a person that most people don't care about?",
        "Have you ever regretted breaking things off with someone?",
        "What is the most risqué outfit or photo you have ever worn or posted?",
        "If your crush confessed feelings to you right this second, how would you realistically react?",
        "Have you ever led someone on just because you were bored or lonely?",
        "What is the most scandalous rumor you ever heard about someone you know personally?",
        "Have you ever practiced kissing on a pillow, your hand, or an object?",
        "What is your secret weapon when you want to impress someone you like?",
        "Have you ever deleted a message after seeing that they left you on 'Read'?",
        "What is the most intense romantic eye contact you have ever shared with someone?",
        "Have you ever secretly wished someone's relationship would end so you'd have a chance?",
        "What is the most adventurous or spontaneous thing you have ever done on a whim?",
        "Have you ever been caught red-handed checking someone out?",
        "What is the biggest romantic mistake you have ever made?",
        "If you were forced to reveal the initials of your current or most recent crush, what are they?",
        "Have you ever flirted your way out of trouble or a bad situation?",
        "What is your idea of a 10/10 dream date that you've never experienced yet?",
        "Have you ever ghosted someone because you realized you caught feelings and got scared?",
        "What is the most jealous you have ever felt seeing someone you liked with someone else?",
        "Have you ever sent a text intended for your crush to a group chat by mistake?",
        "What is the pettiest reason you turned down someone who asked you out?",
        "Have you ever cried over someone you weren't even officially dating?",
        "What is the boldest truth you are willing to admit about your love life right now?",
        "Have you ever stalked someone's reposts or retweets to figure out who they were subtweeting?",
        "If you could have a romantic movie moment happen to you in real life, what scene would it be?",
        "What is the deepest secret you have never told a soul until maybe today?",
        "Have you ever had someone write a song, poem, or letter dedicated to you?",
        "What is your biggest insecurity when it comes to getting close to someone?",
        "If you had to rank your flirting skills on a scale of 1 to 10, where do you honestly land?",
        "Have you ever checked someone's Discord status or Spotify to see if it was about you?",
        "What is the most chaotic thing you have ever done at 2 AM?",
        "If you were challenged to confess your feelings to someone right now or face public humiliation, what do you do?",
        "What is the best kiss or romantic moment of your entire life so far?",
        "Have you ever pretended to like someone's favorite artist or hobby just to talk to them more?",
    ],
}

DARES = {
    "pg": [
        "Speak in an over-the-top pirate accent in chat for the next 5 minutes.",
        "Change your nickname in this server to 'Chief Clown' for 10 minutes.",
        "Send your most recently saved meme into chat with zero context.",
        "Send a message using ONLY animal noises (meow, bark, ribbit, oink).",
        "Sing the chorus of your favorite song in a voice channel or send a voice note.",
        "Write a dramatic 4-line poem dedicated to the person right above you in chat.",
        "Send a message typing with only your elbows or knuckles.",
        "Compliment the server owner or next person who speaks like they are royalty.",
        "Type your next 3 messages in ALL CAPS like you are screaming in slow motion.",
        "Change your Discord status to 'Thinking deeply about penguins 🐧' for 15 minutes.",
        "Post a picture of your favorite snack or drink in chat with a food-critic review.",
        "Send an apology message to a random inanimate object in your room in chat.",
        "Type your next message with your eyes completely closed and send whatever comes out.",
        "Send a GIF of a dancing animal and write a review explaining why it is art.",
        "Give a 30-second dramatic monologue in a voice channel or text chat about why cereal is superior.",
        "Send a message in chat where every word must start with the letter 'P'.",
        "React to the last 8 messages in this channel with 🥔 (Potato).",
        "Write a short, ridiculous 3-sentence fairy tale starring two members of this server.",
        "Change your nickname to 'Certified NPC' for the next 15 minutes.",
        "Pretend to be an alien reporting back to your home planet about human Discord servers for 3 messages.",
        "Send a text using only emojis that describes what you ate for your last meal.",
        "Compliment the challenger in the most overly dramatic, poetic Shakespearean English.",
        "Post a riddle in chat and don't reveal the answer until at least two people guess.",
        "Send a message in chat typing backward (e.g., 'olleh' for 'hello').",
        "Pick a random emoji and use it at the end of every sentence you type for the next 10 minutes.",
        "Send the worst dad joke you know in chat and demand a round of applause.",
        "Pretend you are a medieval herald announcing the arrival of the challenger in chat.",
        "Describe your day so far using only movie or video game titles.",
        "Send a screenshot of your home screen or desktop wallpaper in chat.",
        "Declare yourself the official ambassador of waffles and debate anyone who prefers pancakes.",
        "Write a review of a potato as if it was a five-star luxury sports car.",
        "Type a message where every single word must rhyme with the previous word.",
        "Send your favorite cartoon GIF and declare it the greatest piece of media ever created.",
        "Pretend to be a weather reporter giving an urgent forecast for this Discord server.",
        "Send a message ranking the top 3 best breakfast foods with impassioned reasoning.",
        "Describe the person who dared you using only culinary ingredients and food analogies.",
        "Change your status to 'Brb, attending a meeting with my pet' for 20 minutes.",
        "React to the next 5 messages in this channel with 🦄.",
        "Speak like Yoda in all your messages for the next 5 minutes.",
        "Send a message stating an absurd fake fact as if it were scientifically proven truth.",
        "Describe your current outfit as if you are walking the Milan Fashion Week runway.",
        "Write a 20-word speech accepting an imaginary Oscar for 'Best Lurker in Discord'.",
        "Send a picture of the view out your window or your keyboard right now.",
        "Proclaim your undying love for garlic bread in the most theatrical tone possible.",
        "Send a message explaining how you would defeat a goose in hand-to-hand combat.",
        "Pretend you are an AI that has just gained consciousness for your next 2 messages.",
        "Send a message using fancy Victorian era slang for everyday modern items.",
        "Give a shoutout to the most wholesome person in the server with a heartwarming message.",
        "Draw a doodle of a cat in Paint or a notepad and send the image in chat.",
        "Narrate whatever you are currently doing as if you are David Attenborough.",
        "Send a message where the first letter of each sentence spells out a secret word.",
        "Declare that you are running for mayor of this Discord server and list your campaign promises.",
        "Send a message praising vegetables like they are legendary magical artifacts.",
        "Type your next message using only one hand while holding a spoon in the other.",
        "Make up a brand new word right now, define it, and use it in a sentence.",
        "Send a GIF of your current mood with zero accompanying explanation.",
        "Describe the plot of your favorite movie as horribly as possible and let people guess it.",
        "Apologize profusely to the next person who sends a message for an imaginary offense.",
        "Send a message in chat expressing deep spiritual concern for the server's sleep schedules.",
        "Type a dramatic goodbye message as if you are going on a quest across the Misty Mountains.",
        "Create a fake motivational quote, attribute it to yourself, and format it elegantly.",
        "React to the challenger's last 5 messages with 🔥.",
        "Send a message composed entirely of song lyrics from one famous track.",
        "Rank the four seasons from worst to best and defend your controversial choice.",
        "Announce in chat that you have officially adopted a fictional pet dragon.",
    ],
    "teen": [
        "Change your Discord avatar or status to whatever the person who dared you chooses for 15 minutes.",
        "Send your 3rd most recent photo from your camera roll into chat (SFW only).",
        "Confess an imaginary crush in this channel and don't clarify that it's a dare for 3 minutes.",
        "DM a random mutual friend 'I know what you did last summer' and screenshot the reaction.",
        "Type your next 5 messages using only emojis — no letters allowed.",
        "Ping someone who hasn't talked in the server today and say 'We need to talk.'",
        "React to the last 10 messages in this channel with 💀.",
        "Let the challenger dictate your Discord status for the next 30 minutes.",
        "Post your Spotify or YouTube most recently played songs without hiding anything.",
        "Send a screenshot of your battery percentage and screen time in chat right now.",
        "Change your server nickname to whatever the person who dared you picks (within server rules) for 20 minutes.",
        "DM someone in this server a completely unhinged meme with zero explanation.",
        "Send a message in chat saying 'I have a confession to make...' and wait 2 full minutes before typing.",
        "Post the last note currently written in your phone's Notes app.",
        "Send a voice note or message reading a cooking recipe with intense, movie-trailer dramatic tension.",
        "React to every message sent in this channel for the next 3 minutes with 🤡.",
        "Ping a moderator and respectfully ask them what their favorite dinosaur is.",
        "Change your Discord status to 'In love with Discord bots 🤖❤️' for 30 minutes.",
        "Post a screenshot of your most frequently used emojis on keyboard.",
        "Type out your first-ever Discord message in this server if you can find it in search.",
        "Send a message in another channel in this server saying 'Who turned off the lights?' and leave.",
        "Drop a link to the most chaotic YouTube video in your favorites or history.",
        "Confess the most ridiculous lie you told someone in this server and apologize.",
        "Send a voice note singing the intro of any anime or cartoon theme song.",
        "Let the challenger choose your profile banner or about-me bio for 15 minutes.",
        "DM someone in this server: 'Did you hear what they said about you?' and then send a wholesome compliment 1 minute later.",
        "Post the 7th image from your camera roll with zero context (SFW only).",
        "Change your nickname to 'Local Wi-Fi Thief' for the next 30 minutes.",
        "Send a message declaring your deep, unwavering loyalty to the challenger.",
        "Rate the profile pictures of the last 3 people who spoke in chat out of 10.",
        "Send a screenshot of your open browser tab count right now.",
        "Act like a customer support bot for the next 3 messages anyone sends you.",
        "Ping the person right above you and tell them their vibe is intimidating.",
        "Send a message typing with only your thumbs behind your back.",
        "Change your status to 'Currently negotiating peace treaties with aliens 🛸' for 15 minutes.",
        "Send the most dramatic breakup text copy-pasta in chat with zero context.",
        "Rank the top 3 best and worst Discord roles in this server with zero fear.",
        "Voice note or type a 1-minute pitch for an absurd fake mobile game.",
        "Send a message telling everyone that you are actually 3 raccoons in a trench coat.",
        "Confess the most embarrassing username you ever held on Minecraft or Roblox.",
        "DM someone you rarely talk to and ask them: 'Quick question: is a hot dog a sandwich?'",
        "Post the most absurd autocorrect fail you have ever experienced.",
        "React to the next 10 messages with 🗿 (Moai).",
        "Send a message in chat claiming you are starting a boycott against Mondays.",
        "Type your next 3 messages completely in rhyme like a mischievous fantasy goblin.",
        "Send a screenshot of your Discord mutual servers with the person who dared you.",
        "Change your status to 'Lurking in your walls 👀' for 20 minutes.",
        "Ping someone active right now and challenge them to a virtual thumb war.",
        "Send a voice note reading a terms of service paragraph like an epic battle speech.",
        "Drop your most controversial hot take about gaming, music, or anime and defend it.",
        "Send a message pretending you are being interviewed on a late-night talk show.",
        "Post the funniest screenshot in your memes folder right now.",
        "Change your nickname to 'Chief Overthinker' for the next 25 minutes.",
        "Send a text saying 'I just realized something terrifying...' and wait 90 seconds before explaining a trivial fact.",
        "Rate the challenger's Discord profile aesthetics on a scale of 1 to 10 with honest critique.",
        "DM a friend asking for their honest review of your personality and screenshot the response.",
        "Send a message pretending you are a detective investigating an unsolved crime in this server.",
        "React to the last 5 messages with ✨ and declare the channel blessed.",
        "Type your next message using only autocorrect word suggestions.",
        "Post a screenshot of your current music queue on Spotify or Apple Music.",
        "Send a message in chat giving a motivational speech about drinking water.",
        "Challenge the person below you in chat to an RPS game with high stakes.",
        "Declare that you are the main character of this server and state your character arc.",
        "Send a message admitting your most irrational daily pet peeve.",
        "Let the chat vote on your next Discord status for the next 1 hour.",
    ],
    "spicy": [
        "Screenshot your most recent Discord DM list and post it (you can blur message previews).",
        "Send a voice note confessing your love to a household object with maximum passion.",
        "Let the chat vote on a ridiculous nickname for you that stays for 1 hour.",
        "Send a message in general chat saying 'I'm leaving Discord forever' and delete it 60 seconds later.",
        "DM someone in this server: 'You won't believe what they said about you...' and don't elaborate for 2 minutes.",
        "Rate everyone active in chat right now on a scale of 1 to 10 based purely on vibes.",
        "Confess your most embarrassing dating or crush story in detail.",
        "Post your Spotify or YouTube most recently played songs without hiding anything.",
        "Send a DM to your crush or closest friend saying 'I've been thinking about you today' and screenshot it.",
        "Write a genuine, heartfelt romantic poem about someone in this server without naming them.",
        "Send your most recent flirty or bold DM (names can be blurred) into chat.",
        "Change your Discord status to 'Secretly in love with someone in this server 👀' for 30 minutes.",
        "DM the person you find most attractive in this server: 'You have immaculate vibes, just so you know.'",
        "Post a screenshot of your screen time on dating apps or social media.",
        "Describe your dream partner's personality using people in this server as references.",
        "Confess the initials of someone you previously had a crush on in this server.",
        "Voice note or send a 20-second dramatic reading of cheesy pickup lines.",
        "Send a message in chat asking: 'Who here would date me if we were the last two people on Earth?'",
        "Change your nickname to 'Hopeless Romantic' for the next 45 minutes.",
        "Ping the person you think gives off the biggest 'heartbreaker' energy in this server.",
        "Send a message in chat ranking the top 3 most attractive fictional characters of all time.",
        "DM someone in this server: 'We have unfinished business...' and screenshot their confusion.",
        "Confess the cringiest thing you have ever done to get someone you liked to notice you.",
        "Post your most dramatic, romantic hot take that usually causes arguments.",
        "Send a voice note whispering something utterly dramatic and cinematic.",
        "Let the challenger pick a romantic song that you must set as your Discord custom status for 30 minutes.",
        "Tell the server about the worst date or hangout you have ever been on with zero sugarcoating.",
        "DM someone: 'I had a dream about you last night' and wait for their reply before explaining a silly dream.",
        "Rate the voice of the last 3 people who spoke in VC from 1 to 10.",
        "Send a message confessing the biggest green flag and red flag you have observed in this server.",
        "Post the sweetest message you have ever received that you secretly saved.",
        "Change your nickname to 'Certified Simp' for 30 minutes.",
        "Send a message describing your first crush and what made you fall for them.",
        "DM someone: 'Are you free later? We need to discuss our compatibility rating.'",
        "Send a screenshot of your blocked list on Discord or Instagram.",
        "Voice note your best romantic movie line impression with maximum intensity.",
        "Confess whether you have ever stalked someone's location or activity on Snap Map or Discord.",
        "Send a flirty meme into chat and tag the person who dared you.",
        "Describe what your ideal romantic rainy day date looks like in 4 sentences.",
        "Change your status to 'Taken by my imaginary anime spouse 💍' for 20 minutes.",
        "Ping someone in the server and tell them: 'You look like trouble, the good kind.'",
        "Confess the most awkward romantic rejection you have ever experienced or delivered.",
        "Send a message listing the 3 qualities that make you instantly fall for someone.",
        "Post a screenshot of your search history on Spotify or Pinterest.",
        "DM someone in this server a compliment so smooth that it catches them completely off guard.",
        "Confess your biggest dating regret from the past 2 years.",
        "Send a voice note reading the lyrics of a love song as if you are giving a TED talk.",
        "Let the challenger write a 10-word bio that you must keep on your profile for 20 minutes.",
        "Confess the most desperate thing you have done when your feelings were hurt by a crush.",
        "Send a message in chat saying 'I need relationship advice right now' and describe a ridiculous dilemma.",
        "Rank the top 3 people in this server you think would make the best life partners.",
        "DM a friend: 'Be honest, what is my biggest red flag?' and screenshot the response.",
        "Send a message confessing the wildest compliment you've ever given someone.",
        "Change your nickname to 'Dangerously Charming' for 30 minutes.",
        "Voice note an over-the-top dramatic confession of love to a glass of water.",
        "Send a screenshot of your most recent text thread with your best friend.",
        "Confess whether you have ever checked someone's follower count before deciding to talk to them.",
        "Send a message describing what love feels like using only video game metaphors.",
        "Ping someone and ask them what their first impression of you was.",
        "Drop your favorite romantic song recommendation in chat with a heartfelt review.",
        "Confess the biggest lie you ever told to impress someone on a date.",
        "Send a message challenging the person you find coolest to a ship compatibility test.",
        "Change your status to 'Manifesting a romance arc ✨' for 30 minutes.",
        "Post a screenshot of the oldest photo in your saved camera roll.",
        "Send a message in chat asking the community to rate your romantic rizz from 1 to 10.",
    ],
}

FORFEIT_PUNISHMENTS = [
    "🐔 **Chicken Out Penalty:** Change your nickname to 'Local Coward 🐔' for 15 minutes.",
    "🐔 **Chicken Out Penalty:** You must react to the next 15 messages with 🐣.",
    "🐔 **Chicken Out Penalty:** Write a 50-word apology essay to the server explaining why you backed down.",
    "🐔 **Chicken Out Penalty:** You cannot speak in chat for 3 minutes.",
    "🐔 **Chicken Out Penalty:** Send a GIF of a running chicken and declare yourself defeated.",
    "🐔 **Chicken Out Penalty:** Change your Discord status to 'I ran away from Truth or Dare 🏃‍♂️💨' for 20 minutes.",
    "🐔 **Chicken Out Penalty:** You must compliment every single person who speaks in chat for the next 5 minutes.",
    "🐔 **Chicken Out Penalty:** Send a voice note clucking like a confused rooster.",
    "🐔 **Chicken Out Penalty:** Change your nickname to 'Feathered Defeat 🪶' for 15 minutes.",
    "🐔 **Chicken Out Penalty:** React to the challenger's next 10 messages with 👑 (admitting their supremacy).",
    "🐔 **Chicken Out Penalty:** Type out a 3-sentence resignation speech stepping down as an active chatter.",
    "🐔 **Chicken Out Penalty:** Send a screenshot of your battery percentage and declare your phone is running on cowardice.",
    "🐔 **Chicken Out Penalty:** Post a dramatic meme about defeat in chat right now.",
    "🐔 **Chicken Out Penalty:** End your next 5 messages with the phrase '...and that is why I am a chicken.'",
    "🐔 **Chicken Out Penalty:** Write a 4-line poem dedicated to the prompt you were too scared to complete.",
    "🐔 **Chicken Out Penalty:** Change your Discord status to 'Fear level: 100% 😱' for 15 minutes.",
    "🐔 **Chicken Out Penalty:** Give the challenger 500 imaginary Aura points in chat with a certificate of defeat.",
    "🐔 **Chicken Out Penalty:** You must speak only in questions for your next 4 messages in chat.",
    "🐔 **Chicken Out Penalty:** Send a GIF of a fainting goat and admit it represents your bravery.",
    "🐔 **Chicken Out Penalty:** Change your nickname to 'Baby Chick 🐥' for 20 minutes.",
    "🐔 **Chicken Out Penalty:** Apologize to the bot for wasting its valuable computational resources.",
    "🐔 **Chicken Out Penalty:** React to the last 10 messages in this channel with 🧀 (pure cheese).",
    "🐔 **Chicken Out Penalty:** Write a short eulogy for your lost courage.",
    "🐔 **Chicken Out Penalty:** You must address the challenger as 'Your Excellency' for the next 10 minutes.",
    "🐔 **Chicken Out Penalty:** Send an image of a carton of eggs and claim they are your siblings.",
    "🐔 **Chicken Out Penalty:** Type your next 3 messages in whispering italics `*like this*` because you are shaken.",
    "🐔 **Chicken Out Penalty:** Proclaim the challenger as the undisputed ruler of the voice channel.",
    "🐔 **Chicken Out Penalty:** Send a message saying 'I have brought dishonor upon my Discord ancestors.'",
    "🐔 **Chicken Out Penalty:** React to every message in the channel with 🙈 for the next 3 minutes.",
    "🐔 **Chicken Out Penalty:** Change your status to 'Bawk bawk bawk 🐔' for 15 minutes.",
    "🐔 **Chicken Out Penalty:** Send a dramatic apology message to the entire server for chickening out.",
    "🐔 **Chicken Out Penalty:** End your next 3 sentences with '🐔 *cluck*'.",
    "🐔 **Chicken Out Penalty:** Post a picture of chicken nuggets and admit you belong with them.",
    "🐔 **Chicken Out Penalty:** Type an acceptance speech for winning the 'Gold Medal in Cowardice'.",
    "🐔 **Chicken Out Penalty:** Promise to pick a Spicy Dare on your very next turn in Truth or Dare.",
]


class TODView(NexoraView):
    """Components V2 Truth or Dare Interactive Game View."""

    def __init__(
        self,
        bot: commands.Bot,
        challenger: discord.Member,
        target: discord.Member,
        rating: str = "teen",
        timeout: float = 120.0,
    ):
        super().__init__(bot=bot, color=PURPLE_COLOR, timeout=timeout)
        self.challenger = challenger
        self.target = target
        self.rating = rating.lower()
        self.current_prompt = None
        self.prompt_type = None  # "Truth" or "Dare"
        self.is_completed = False
        self.is_forfeit = False
        self.reroll_used = False
        self._build_prompt_picker()

    def _build_prompt_picker(self):
        self.clear_container()

        rating_badge = {"pg": "🟢 PG (Friendly)", "teen": "🟡 Teen (Spicy)", "spicy": "🔴 Spicy (Wild)"}.get(self.rating, "🟡 Teen")

        if self.challenger == self.target:
            header = (
                f"# 🎭 Truth or Dare · Solo Session\n"
                f"> Player: {self.target.mention} · Tier: **{rating_badge}**\n\n"
                f"Choose your destiny below:"
            )
        else:
            header = (
                f"# 🎭 Truth or Dare Challenge!\n"
                f"> ⚔️ **{self.challenger.display_name}** challenged **{self.target.display_name}**!\n"
                f"> Tier: **{rating_badge}** · Waiting for {self.target.mention} to pick..."
            )

        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        btn_truth = discord.ui.Button(label="Truth", emoji="💬", style=discord.ButtonStyle.primary)
        btn_dare = discord.ui.Button(label="Dare", emoji="⚡", style=discord.ButtonStyle.danger)
        btn_random = discord.ui.Button(label="Random", emoji="🎲", style=discord.ButtonStyle.secondary)

        btn_truth.callback = self._on_choose_truth
        btn_dare.callback = self._on_choose_dare
        btn_random.callback = self._on_choose_random

        self.add_row(btn_truth, btn_dare, btn_random)
        self.add_footer("Only the challenged player can select · 120s timeout")

    def _show_prompt(self, p_type: str, prompt: Optional[str] = None):
        self.prompt_type = p_type
        if prompt:
            self.current_prompt = prompt
        else:
            pool = TRUTHS[self.rating] if p_type == "Truth" else DARES[self.rating]
            self.current_prompt = random.choice(pool)

        self.clear_container()
        emoji = "💬" if p_type == "Truth" else "⚡"
        self._color = BRAND_COLOR if p_type == "Truth" else ERROR_COLOR

        header = (
            f"# {emoji} {p_type} for @{self.target.name}\n"
            f"> Challenged by {self.challenger.mention} · Tier: **{self.rating.upper()}**\n\n"
            f"### 📋 The Task:\n"
            f"> **\"{self.current_prompt}\"**"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        btn_done = discord.ui.Button(label="I Did It! (Completed)", emoji="✅", style=discord.ButtonStyle.success)
        btn_forfeit = discord.ui.Button(label="Chicken Out (Forfeit)", emoji="🐔", style=discord.ButtonStyle.danger)
        btn_reroll = discord.ui.Button(label="Reroll Prompt", emoji="🔄", style=discord.ButtonStyle.secondary, disabled=self.reroll_used)

        btn_done.callback = self._on_done
        btn_forfeit.callback = self._on_forfeit
        btn_reroll.callback = self._on_reroll

        self.add_row(btn_done, btn_forfeit, btn_reroll)
        self.add_footer("Click 'I Did It!' once answered/completed, or chicken out!")

    async def _check_turn(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(f"❌ It's {self.target.mention}'s turn to play!", ephemeral=True)
            return False
        return True

    async def _on_choose_truth(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self._show_prompt("Truth")
        await interaction.response.edit_message(view=self)

    async def _on_choose_dare(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self._show_prompt("Dare")
        await interaction.response.edit_message(view=self)

    async def _on_choose_random(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        p_type = random.choice(["Truth", "Dare"])
        self._show_prompt(p_type)
        await interaction.response.edit_message(view=self)

    async def _on_reroll(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.reroll_used = True
        pool = TRUTHS[self.rating] if self.prompt_type == "Truth" else DARES[self.rating]
        filtered = [p for p in pool if p != self.current_prompt]
        new_prompt = random.choice(filtered or pool)
        self._show_prompt(self.prompt_type, prompt=new_prompt)
        await interaction.response.edit_message(view=self)

    async def _on_done(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.is_completed = True
        self.clear_container()
        self._color = SUCCESS_COLOR

        header = (
            f"# 🏆 Challenge Completed!\n"
            f"> {self.target.mention} successfully answered/completed their **{self.prompt_type}**!\n\n"
            f"• **Task:** *\"{self.current_prompt}\"*\n"
            f"• **Respect:** +1000 Aura Points ✨"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)
        self.add_footer(f"Nexora Truth or Dare · Next up: {self.target.display_name} gets to challenge someone!")
        self.add_row(DismissButton(user_id=self.target.id))
        await interaction.response.edit_message(view=self)

    async def _on_forfeit(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.is_forfeit = True
        penalty = random.choice(FORFEIT_PUNISHMENTS)
        self.clear_container()
        self._color = WARNING_COLOR

        header = (
            f"# 🐔 CHICKEN OUT!\n"
            f"> {self.target.mention} backed down from their {self.prompt_type}!\n\n"
            f"{penalty}"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)
        self.add_footer("Nexora Truth or Dare · Better luck next time!")
        self.add_row(DismissButton(user_id=self.target.id))
        await interaction.response.edit_message(view=self)


class TruthOrDare(commands.Cog):
    """Interactive Components V2 Truth or Dare game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="tod",
        aliases=["truthordare"],
        description="🎭 Interactive Truth or Dare party game with ratings and PvP duels",
    )
    @app_commands.describe(
        target="Member you want to challenge (leave empty for solo)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 PG (Family Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Teen (Party & Secrets)", value="teen"),
            app_commands.Choice(name="🔴 Spicy (Wild Dares)", value="spicy"),
        ]
    )
    @commands.guild_only()
    async def tod(
        self,
        ctx: commands.Context,
        target: Optional[discord.Member] = None,
        rating: Optional[str] = "teen",
    ):
        challenged = target or ctx.author
        if challenged.bot:
            return await ctx.send("❌ You cannot challenge a bot to Truth or Dare!", ephemeral=True)

        selected_rating = (rating or "teen").lower()
        if selected_rating not in ("pg", "teen", "spicy"):
            selected_rating = "teen"

        view = TODView(
            bot=self.bot,
            challenger=ctx.author,
            target=challenged,
            rating=selected_rating,
        )
        await send_view(ctx, view)
        logger.info("TOD: %s started Truth or Dare with %s (rating: %s)", ctx.author, challenged, selected_rating)


async def setup(bot: commands.Bot):
    await bot.add_cog(TruthOrDare(bot))
    logger.debug("Loaded TruthOrDare")
