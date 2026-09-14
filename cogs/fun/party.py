"""
cogs/fun/party.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Social & Party Hub
Interactive social entertainment commands built on Components V2:
  • pp: Fake measurement scanner with hilarious scales & ratings
  • iq: Random IQ generator with brain tiers, stats & diagnoses
  • vibe: Solo daily vibe check or Duo compatibility dynamic
  • fortune: Cursed fortune teller with ominous & hilarious prophecies
  • npc: Transforms custom messages or users into retro RPG NPC dialogues
  • compliment: Wholesome, heartwarming & witty compliments
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    CYAN_COLOR,
    ERROR_COLOR,
    PREMIUM_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    progress_bar,
    send_view,
)

logger = logging.getLogger(__name__)

PINK_COLOR = 0xFF7597


# ══════════════════════════════════════════════════════════════════════════════
# DATA POOLS
# ══════════════════════════════════════════════════════════════════════════════

PP_TIERS = [
    (
        0, 1, "🔬 Quantum Particle",
        [
            "Scientists require the Large Hadron Collider to detect even a trace of this.",
            "Subatomic particles are feeling second-hand embarrassment right now.",
            "Theoretical physicists have published papers debating if this even exists in 3D spacetime.",
            "Planck length is currently filing a trademark infringement lawsuit.",
            "Magnifying glasses and electron microscopes have both officially resigned.",
        ],
        -500,
    ),
    (
        2, 4, "🤏 Pocket Edition",
        [
            "Compact, highly aerodynamic, extremely low drag coefficient.",
            "Travel-sized for your convenience. TSA pre-check approved.",
            "Fits comfortably in the glove compartment next to the spare fuses.",
            "Eco-friendly build with minimal material waste. Certified sustainable.",
            "Designed for rapid deployment and stealth operations.",
        ],
        +150,
    ),
    (
        5, 7, "📐 Standard Issue",
        [
            "Statistically respectable, dependable factory build. Gets the job done.",
            "ISO-9001 certified. The trusty daily driver of physical metrics.",
            "Middle of the bell curve. Honest work from an honest specimen.",
            "No federal permits required. Dependable, civic-minded engineering.",
            "Approved by municipal inspectors with zero safety citations.",
        ],
        +500,
    ),
    (
        8, 10, "🚀 Heavy Artillery",
        [
            "Requires a class-3 federal permit, safety goggles, and ear protection.",
            "Department of Defense has briefly flagged this channel for surveillance.",
            "Excessive recoil detected. Proper stance and footing strongly advised.",
            "Local seismographs registered a mild tremor when this metric was loaded.",
            "May cause structural cracks in drywall if handled without caution.",
        ],
        +1200,
    ),
    (
        11, 14, "🌌 Gravitational Anomaly",
        [
            "Creates a noticeable gravitational bend in local spacetime curvature.",
            "Nearby celestial bodies are beginning to alter their orbital trajectories.",
            "Einstein specifically warned mankind about this in his unpublished journals.",
            "Light cannot escape its immediate proximity. Pure event-horizon energy.",
            "Scientists at MIT are requesting an emergency research grant to study this.",
        ],
        +3500,
    ),
    (
        15, 25, "🦕 Mythical Leviathan",
        [
            "Ancient Mesopotamian stone tablets prophesied this magnitude. Server trembling.",
            "The tectonic plates under the datacenter just shifted 3 inches to the left.",
            "A legendary relic from the prehistoric epoch. Bards will sing of this.",
            "Requires its own dedicated zip code and municipal water supply.",
            "The server host just contacted emergency services out of sheer awe.",
        ],
        +10000,
    ),
]

IQ_TIERS = [
    (
        10, 45, "Room Temperature IQ 🌡️",
        [
            "Breathes manually while thinking. Forgets why they walked into a room 8 times daily.",
            "Blows on ice cream to cool it down. Stares at frozen pizza awaiting instructions.",
            "Pushes doors clearly marked 'PULL' with increasing, bewildered aggression.",
            "Uses their phone flashlight to search under the bed for their missing phone.",
            "Tries to swipe left on printed magazine pages and gets visibly confused.",
        ],
        "Cold & Drafty",
    ),
    (
        46, 75, "Single Braincell Orange Cat 🐱",
        [
            "Currently awaiting their turn with the communal server braincell. Connection timeout.",
            "Head completely empty, absolutely zero thoughts, pristine smooth brain perfection.",
            "Stares intently at the ceiling fan for 45 minutes contemplating nothing.",
            "Chases red laser pointers across Discord text channels with fervent loyalty.",
            "Buffer underflow detected in cognitive subsystem. Rebooting with treats.",
        ],
        "Void Noises",
    ),
    (
        76, 99, "Certified Goober 🥔",
        [
            "Has plenty of heart and enthusiasm, but executive function is taking a nap.",
            "Answers 'you too!' when the waiter tells them to enjoy their meal.",
            "Repeats a joke three times because the first two people didn't laugh.",
            "Puts milk in the pantry and cereal in the refrigerator without noticing.",
            "Watches microwave countdown like an intense Hollywood bomb defusal scene.",
        ],
        "Wholesome Clueless",
    ),
    (
        100, 125, "Functional Human Specimen 🧠",
        [
            "Understands basic cause and effect. Refrains from microwaving aluminum foil.",
            "Possesses working common sense and occasionally remembers where they left their keys.",
            "Can follow a recipe without accidentally burning water or causing kitchen alarms.",
            "Solid, dependable baseline humanity. Immune to most obvious Nigerian prince scams.",
            "Capable of navigating an IKEA store without filing missing person reports.",
        ],
        "Solid Normie",
    ),
    (
        126, 160, "High-Performance Thinker ⚡",
        [
            "Calculates the tip mentally in 0.3 seconds flat. Sees through reality's matrix code.",
            "Wins arguments in their head and then repeats them aloud with lethal precision.",
            "Spots plotholes in movies before the opening credits have finished rolling.",
            "Overthinks a 3-word text message for 4 hours and ends up sending 'ok'.",
            "Processes complex social dynamics at 240 FPS while pretending to be asleep.",
        ],
        "Sharp Operator",
    ),
    (
        161, 215, "Megamind Tactician 🛸",
        [
            "IQs rivaling historical prodigies. Playing 5D chess while others eat crayons.",
            "Predicts the stock market using tea leaves, lunar cycles, and Discord memes.",
            "Has already thought of 14 counter-arguments to whatever you're about to say.",
            "Plans their daily schedule down to the microsecond like a NASA launch trajectory.",
            "Communicates primarily in subtle nods and condescending raised eyebrows.",
        ],
        "Prodigy",
    ),
    (
        216, 350, "Ascended Galaxy Brain 🌌",
        [
            "Communicates in 5th-dimensional telepathic pulses. Physical laws of physics are optional.",
            "Can smell color, taste mathematical equations, and hear Wi-Fi frequencies.",
            "Has solved cold fusion three times on a napkin but lost the napkin in the laundry.",
            "Transcended mortal intellect; now spends 90% of their energy shitposting on Discord.",
            "The universe occasionally consults them when quantum mechanics starts glitching.",
        ],
        "Transcendent",
    ),
]

VIBE_SOLO_POOL = [
    ("🦝 Chaotic Raccoon", "Scavenging snacks at 3 AM, pure feral determination, unbothered by laws of society."),
    ("🦥 Zen Capybara", "Zero enemies, infinite chill, floating peacefully down the stream of existence."),
    ("🐕 Golden Retriever", "Tail wagging enthusiastically, zero evil intentions, easily excited by literally everything."),
    ("🐈 Void Cat", "Staring into dark corners at unseen cosmic entities, judging everyone with regal silence."),
    ("🦆 Menace Goose", "Peace was never an option. Honking aggressively at minor daily inconveniences."),
    ("🦉 Cryptid Night Owl", "Awake exclusively between 1 AM and 5 AM dispensing unhinged late-night wisdom."),
    ("🐼 Slumbering Panda", "Rolling slowly down grassy hills, consuming carbs, scheduling strategic naps."),
    ("🦊 Cunning Fox", "Scheming something mildly devious with a suspicious, knowing grin across their face."),
    ("🦦 Wholesome Otter", "Holding hands with friends while sleeping so you don't drift apart in the current."),
    ("🦔 Cozy Hedgehog", "Prickly on the outside until warm blankets and favorite comfort snacks are introduced."),
    ("🐝 Overcaffeinated Bee", "Buzzing frantically across 18 browser tabs with 3% phone battery remaining."),
    ("🦭 Round Seal", "Maximum surface-area comfort, bouncing gently through existential life questions."),
    ("🐧 Dapper Penguin", "Looking dressed for a black-tie gala while sliding on belly across the ice."),
    ("🐺 Lone Wolf", "Brooding in the server corner with dramatic lighting, secretly craving affection."),
    ("🐢 Contemplative Tortoise", "Moving at 0.2 mph, outliving all drama, chewing a leaf in complete peace."),
    ("🦜 Screaming Cockatoo", "Repeating funny words at 120 decibels, demanding attention with chaotic energy."),
    ("🐸 Cozy Frog", "Sitting on a lily pad in the rain, completely unbothered by global geopolitical events."),
    ("🐨 Sleepy Koala", "Consuming leaves, sleeping 20 hours a day, zero stressful thoughts behind those eyes."),
    ("🐬 Mischievous Dolphin", "Doing flips in chat, laughing playfully, secretly smarter than everyone in VC."),
    ("🦀 Dancing Crab", "Rave music playing perpetually in head, scuttling sideways out of awkward situations."),
    ("🦄 Mythical Unicorn", "Rare, majestic, sparkling with glitter, probably running on 2 hours of sleep."),
    ("🐙 Multi-Tasking Octopus", "Handling 8 different Discord arguments at once while opening a jar of pickles."),
    ("🦖 Feral T-Rex", "Tiny arms, huge roars, ready to knock over furniture if provoked before breakfast."),
    ("🐻 Gentle Bear", "Wants to hibernate until May, but will offer bone-crushing warm hugs if approached."),
    ("🦩 Glamorous Flamingo", "Standing on one leg, showing off exquisite style, ignoring all haters effortlessly."),
    ("🐿️ Hoarding Squirrel", "Has saved 4,000 memes on their phone that they will never look at again."),
    ("🦇 Goth Fruit Bat", "Hanging upside down in a cozy cave, listening to darkwave, eating fresh mango."),
    ("🦈 Smooth Shark", "Gliding effortlessly through server waters, looking sharp and completely confident."),
    ("🦙 Dramatic Llama", "Spitting facts, giving side-eye to low-effort messages, majestic woolly posture."),
    ("🦨 Stinky Skunk", "Leaves a memorable impression wherever they go; enemies think twice before crossing."),
    ("🦎 Sunbathing Lizard", "Absorbing warm vibes from a heated rock, blinking slowly once every 4 minutes."),
    ("🦡 Honey Badger", "Does not care. Simply does not care. Walks through bee swarms for a quick snack."),
    ("🦫 Industrious Beaver", "Building dams, hyper-focusing on a random project for 14 hours straight."),
    ("🐆 Midnight Panther", "Moving in silent stealth, striking with witty remarks when nobody expects it."),
    ("🦩 Party Parrot", "Head bobbing perpetually to an imaginary EDM beat, ultimate hype machine."),
    ("🐌 Patient Snail", "Carrying their whole cozy home on their back, arriving precisely when they mean to."),
    ("🐘 Gentle Elephant", "Never forgets a server inside joke from 3 years ago; massive emotional wisdom."),
    ("🦒 Tall Giraffe", "Head in the clouds, looking down at server arguments from an elevated perspective."),
    ("🦘 Bouncy Kangaroo", "Jumping straight into conversations with intense energy, boxing gloves equipped."),
    ("🦚 Proud Peacock", "Spreading vibrant feathers, demanding appreciation for their new avatar and banner."),
    ("🧙 Mysterious Cryptid", "Sightings reported near voice channels at 4 AM; leaves behind blurry photos and lore."),
    ("☕ Caffeinated Goblin", "Three espresso shots deep, talking at 1.75x speed, vibrating into another dimension."),
    ("🌙 Astral Dreamer", "Lost in daydreams about fantasy worlds, stargazing instead of studying or sleeping."),
    ("🛋️ Professional Couch Potato", "Fused with the cushions, holding remote control like an ancient staff of power."),
    ("⚡ Lightning Bolt", "Pure spontaneous electricity, appears out of nowhere, delivers punchline, vanishes."),
    ("🍃 Autumn Breeze", "Crisp, refreshing, smelling of pumpkin spice and cozy knit sweaters."),
    ("🔥 Bonfire Spirit", "Warming up the entire chat, roasting marshmallows, telling captivating ghost stories."),
    ("🧊 Glacier Ice", "Cool, composed, unshakeable demeanor; never seen breaking a sweat under pressure."),
    ("🌸 Cherry Blossom", "Delicate, aesthetic, spreading gentle positivity and sweet vibes wherever they land."),
    ("🎲 Chaos Die", "Every action is determined by a random d20 roll; completely unpredictable trajectory."),
]

VIBE_DUO_ARCHETYPES = [
    (
        90, 100, "🌟 Soulbound Chaos Twins",
        [
            "You two share a single collective braincell and pass it back and forth like a hot potato. Completely unstoppable.",
            "An unholy alliance of synchronized mischief. When you both enter VC, everyone else checks the exit doors.",
            "You finish each other's sentences, steal each other's snacks, and laugh at jokes that haven't even been spoken aloud.",
            "Cosmic soul-twins operating on a telepathic frequency so dense it disrupts local Wi-Fi networks.",
        ],
    ),
    (
        75, 89, "🔥 Dynamic Menace Duo",
        [
            "When you two enter a voice channel together, moderators immediately start double-checking backup server logs.",
            "A high-octane partnership of pure entertainment. You could start an impromptu podcast and draw 10,000 listeners.",
            "One provides the absurd idea, the other provides the tactical execution. Criminal masterminds in training.",
            "Electric synergy. You amplify each other's chaotic traits until the entire server is cheering.",
        ],
    ),
    (
        50, 74, "⚡ Chaos Goblin & Weary Handler",
        [
            "One starts fires with gasoline and joy; the other sighs deeply while carrying the heavy-duty fire extinguisher.",
            "The classic sitcom balance: an energetic golden retriever paired with a tired, affectionate black cat.",
            "One says 'Hear me out, what if we jump?' and the other prepares the emergency first aid kit.",
            "A relationship built on mutual dependency: one needs a leash, and the other needs some excitement in life.",
        ],
    ),
    (
        25, 49, "🌪️ Walking Argument Machine",
        [
            "Will aggressively debate whether cereal is technically a soup for 4 consecutive hours, then order pizza together.",
            "Bickering like an old married couple since day one. Nobody else can follow the logic of your feuds.",
            "High friction, high entertainment value. You disagree on 95% of life, but would defend each other to the death.",
            "Your conversations look like courtroom trials, but with zero legal consequences and more memes.",
        ],
    ),
    (
        0, 24, "💀 Mutual Restraining Order",
        [
            "Two federal agents are currently assigned to monitor your direct messages with profound, furrowed-brow concern.",
            "Pure anti-matter collision. The server host cooling fans spin up to maximum RPM when you two type simultaneously.",
            "Opposite ends of every known human spectrum. A miracle that you haven't vaporized each other yet.",
            "The diplomatic treaty keeping you two in the same server is thinner than single-ply toilet paper.",
        ],
    ),
]

FORTUNES = [
    ("Tomorrow at 3:14 PM, you will hear a mysterious crunch under your shoe that you will never identify.", "Avoid stepping near mysterious crunchy shadows.", "A half-eaten bag of sour gummies.", "Mild Chaos"),
    ("A stray cat will look you in the eyes tomorrow with far too much human understanding.", "Do not challenge the cat to a stare-down.", "A shiny bottlecap.", "Eerie Awakening"),
    ("You are 84% more likely to drop your phone directly onto your nose tonight in bed.", "Keep your phone at a safe 45-degree angle.", "A soft pillow shield.", "Physical Embarrassment"),
    ("An unopened browser tab from 3 months ago is silently weeping for your return.", "Check your background chrome processes.", "A bookmark you forgot.", "Digital Guilt"),
    ("You will soon wave back enthusiastically at someone who was actually waving to the person behind you.", "Prepare to pretend you were stretching your arm.", "Dark sunglasses.", "Social Catastrophe"),
    ("Your socks will feel perpetually 7% damp tomorrow, regardless of climate or footwear.", "Wear double wool socks as spiritual armor.", "A dry towel.", "Unspeakable Annoyance"),
    ("A microwave will beep at 3:00 AM with absolutely nothing inside. Do not open the door.", "Ignore the spectral popcorn.", "A flashlight with 1 battery.", "Paranormal Menace"),
    ("Someone is explaining your exact personality to an AI right now with mixed emotions.", "Act normal so the algorithm gets confused.", "A tin foil hat.", "Algorithmic Paranoia"),
    ("You will pour milk before realizing you have only 3 pieces of cereal remaining in the box.", "Always inspect the box volume first.", "A solitary spoon.", "Kitchen Despair"),
    ("A spider in your room has officially declared you an acceptable roommate. Rent is overdue.", "Do not disturb the corner web.", "A tiny broom.", "Spiritual Compact"),
    ("Your next sneeze will be stolen by an unseen presence right as you prepare for it.", "Breathe through your nose calmly.", "A tissue box.", "Unresolved Tension"),
    ("You will think of the ultimate comeback to an argument that ended 4 years ago.", "Do not text them at 2 AM with it.", "A shower thought notebook.", "Delayed Triumph"),
    ("You will find an unread Discord ping that turns out to be an @everyone announcement about server rules.", "Disable notification badges immediately.", "A mute button.", "Crushed Hopes"),
    ("Your earbuds will snag on a door handle and violently rip from your ears tomorrow morning.", "Tuck your wires inside your shirt like a secret agent.", "A wireless Bluetooth case.", "Auditory Rage"),
    ("An ice cube will slide down into your throat whole, giving you 4 seconds of pure panic.", "Chew your ice responsibly.", "A warm mug of tea.", "Cold Shock"),
    ("You will accidentally open your front-facing camera in bad lighting and question your entire genetic lineage.", "Look away immediately from the screen.", "A flattering filter.", "Ego Demolition"),
    ("A stranger will sneeze near you and say 'Excuse you' instead of 'Excuse me'.", "Look at them with unblinking bewilderment.", "Hand sanitizer.", "Etiquette Breakdown"),
    ("You will type out a 4-paragraph impassioned essay in chat, then delete it and type 'lol true'.", "Protect your energy from internet arguments.", "The Backspace key.", "Conversational Fatigue"),
    ("A phantom vibration in your pocket will make you check your phone 12 times for zero messages.", "Accept that your leg is hallucinating.", "A phone in 'Do Not Disturb' mode.", "Phantom Loneliness"),
    ("Tomorrow, your favorite song will be ruined by being used in a bizarre pharmaceutical commercial.", "Never watch cable television again.", "Noise-cancelling headphones.", "Artistic Defilement"),
    ("You will push a door with immense confidence, only to realize the giant sign says 'SLIDE'.", "Laugh nervously and look around for witnesses.", "A pair of reading glasses.", "Mechanical Defeat"),
    ("A mysterious single unmatching sock will appear in your laundry basket from an unknown dimension.", "Do not attempt to find its origin.", "A drawer of solitary socks.", "Interdimensional Leak"),
    ("You will bite the inside of your cheek today. And then bite the exact same spot 2 hours later.", "Eat with slow, meditative caution.", "An ice cube.", "Self-Inflicted Betrayal"),
    ("Your computer will attempt an involuntary 45-minute update right when you need to submit something.", "Save your files every 90 seconds.", "An external hard drive.", "Operating System Malice"),
    ("Someone you barely know will ask you for your honest opinion on something terrible they created.", "Prepare a diplomatic 'It's so unique!' response.", "A poker face.", "Moral Dilemma"),
    ("You will wake up 3 minutes before your alarm goes off, fully refreshed, and ruin it by going back to sleep.", "Get out of bed immediately upon waking.", "A loud rooster sound effect.", "Sleep Cycle Tragedy"),
    ("A pigeon will make prolonged, intense eye contact with you and nod slowly.", "Acknowledge the avian operative with a subtle nod.", "A handful of breadcrumbs.", "Feathered Espionage"),
    ("You will search for your sunglasses while they are resting directly on top of your head.", "Pat down your scalp before causing a scene.", "A handheld mirror.", "Perceptual Blindness"),
    ("Your favorite snack will change its packaging to 'New & Improved Recipe' and taste strictly worse.", "Stockpile the original formula while you can.", "A vintage cardboard box.", "Culinary Heartbreak"),
    ("You will enthusiastically recommend a movie to a friend, watch it together, and realize it's agonizingly boring.", "Claim the director's cut was better.", "A fast-forward button.", "Cinephile Regret"),
    ("Your phone will slip between the car seat and the center console into the void of no return.", "Do not reach blindly into the crumb abyss.", "A pair of long kitchen tongs.", "Automotive Purgatory"),
    ("A piece of clothing you thought was lost forever will reappear in the exact center of your floor.", "Thank the house gnomes politely.", "A clothes hanger.", "Fey Mischief"),
    ("You will misread a restaurant menu item and order something that arrives on fire.", "Enjoy the unintentional pyrotechnics.", "A fire extinguisher.", "Flaming Surprise"),
    ("A captcha will accuse you of being a robot, and deep down, you will briefly question if it is right.", "Click all the traffic lights with human pride.", "A captcha bypass token.", "Existential Crisis"),
    ("You will receive a spam phone call from your own area code and answer it in an accent.", "Commit to the persona until they hang up.", "A fake mustache.", "Telephonic Theatre"),
    ("Your shoe lace will come undone 6 consecutive times on a wet muddy sidewalk.", "Tie a triple fisherman's knot immediately.", "Velcro straps.", "Footwear Treachery"),
    ("You will start drinking a cold beverage expecting soda, but it will be iced tea, startling your soul.", "Inspect the glass contents with suspicion.", "A labeled coaster.", "Sensory Whammy"),
    ("A moth will flutter aggressively toward your screen at 1:45 AM and hit you directly in the forehead.", "Turn down screen brightness.", "A bug zapper.", "Nocturnal Assault"),
    ("You will attempt to parallel park and an entire audience of patio diners will watch in dead silence.", "Abortion of maneuver and drive around the block.", "A backup camera.", "Public Performance"),
    ("You will find a $5 bill in an old jacket, immediately spend it on gum, and drop the gum.", "Hold tight to your paper currency.", "A deep zipped pocket.", "Fleeting Prosperity"),
    ("An NPC in a video game will glitch into a wall and stare directly at your camera soul.", "Restart the game client immediately.", "A quicksave file.", "Fourth-Wall Rupture"),
    ("You will sneeze three times in rapid succession, prompting someone to say 'God bless you, okay stop.'", "Accept your nasal limitation.", "A handkerchief.", "Respiratory Excess"),
    ("Your zipper will be down during an important conversation, but nobody will tell you until 3 hours later.", "Check your fly every 30 minutes like clockwork.", "A long winter trenchcoat.", "Wardrobe Malfunction"),
    ("You will accidentally hit 'Call' on a contact while trying to scroll through your phone log.", "Hang up within 0.2 seconds and turn on Airplane mode.", "Quick reflexes.", "Cardiac Arrest"),
    ("A scented candle will claim to smell like 'Ocean Breeze' but will smell exclusively like laundry soap.", "Extinguish the deceptive wax.", "A window fan.", "Olfactory Deception"),
    ("You will make a joke in chat that is so dry everyone will think you are having a mental breakdown.", "Follow up with a clown emoji immediately.", "A sarcasm tag (/s).", "Deadpan Disaster"),
    ("Your shower temperature will fluctuate between liquid magma and Antarctic iceberg in 0.5 seconds.", "Do not touch the temperature knob with wet hands.", "A bath thermometer.", "Plumbing Warfare"),
    ("You will try to quietly open a bag of chips in a silent room and it will sound like thunder.", "Crush the bag boldly without fear.", "Pre-opened snack bowls.", "Acoustic Betrayal"),
    ("A song you hated 5 years ago will suddenly become your favorite earworm for 72 straight hours.", "Accept your questionable character evolution.", "An earplug set.", "Musical Stockholm"),
    ("You will attempt to peel an orange and the peel will spray juice directly into your left eyeball.", "Aim citrus fruits away from your optical sensors.", "Safety goggles.", "Acidic Retaliation"),
    ("A spider will descend from the ceiling directly between your face and your computer screen.", "Evacuate the room and surrender sovereignty.", "A glass cup and paper.", "Arachnid Diplomacy"),
    ("You will forget someone's name 4 seconds after they introduce themselves to you with a handshake.", "Refer to them as 'friend', 'chief', or 'boss' forever.", "A name badge.", "Cognitive Evaporation"),
    ("Your phone will charge to 99% and refuse to hit 100% for 45 minutes out of spite.", "Unplug the cable and accept the imperfection.", "A wireless charging pad.", "Battery Stubbornness"),
    ("You will hear your own voice on a recording and wonder how anyone tolerates listening to you speak.", "Voice pitch is an illusion of skull acoustics.", "A podcast microphone.", "Auditory Dysphoria"),
    ("An unopened bag of bread will grow a patch of blue mold 10 minutes before you make a sandwich.", "Inspect both sides of every slice diligently.", "A toaster oven.", "Fungal Preemption"),
    ("You will walk out of the grocery store and realize you bought 4 snacks and none of the groceries you needed.", "Return inside with your head hung low.", "A handwritten shopping list.", "Impulse Defeat"),
    ("A fly will buzz around your head for 2 hours, land on your hand, and dodge your slap effortlessly.", "Do not engage the master of aerodynamics.", "A rolled-up magazine.", "Insect Humiliation"),
    ("You will try to blow out a candle and accidentally spit on it, extinguishing it with indignity.", "Use a candle snuffer like civilized royalty.", "A wick trimmer.", "Respiratory Mishap"),
    ("You will dream of drinking water, wake up with a mouth as dry as the Mojave desert, and knock over your glass.", "Keep a sealed water bottle on your nightstand.", "A bendy straw.", "Hydration Quest"),
    ("The universe will present you with an impossible dilemma tomorrow: choose the Option B.", "Always trust Option B when spirits whisper.", "A silver two-sided coin.", "Cosmic Synchronicity"),
]

NPC_ARCHETYPES = [
    "Elderly Village Blacksmith",
    "Suspicious Alleyway Merchant",
    "Town Guard (Took Arrow to Knee)",
    "Mysterious Cloaked Mage",
    "Overworked Tavern Keeper",
    "Feral Goblin Scavenger",
    "High Elf Bureaucrat",
    "Lost Adventurer With Broken Map",
    "Sentient Talking Broom",
    "Grumpy Alchemist Who Hates Customers",
    "Retired Dragon In Disguise",
    "Cryptid Swamp Witch",
    "Bard Who Only Knows One Chord",
    "Underground Sewer King",
    "Paladin With Extreme Hero Complex",
    "Cursed Skeleton Seeking Moisturizer",
    "Traveling Potion Salesman",
    "Overly Enthusiastic Quest Giver",
    "Dungeon Janitor With Heavy Mop",
    "Suspiciously Intelligent Farm Pig",
    "Pirate Captain Who Lost Their Ship",
    "Cosmic Space Nomad",
    "Bored Gatekeeper With Riddle Book",
    "Anxious Apprentice Wizard",
    "Time Traveler Trapped In The Wrong Century",
    "Cynical Street Urchin With Stolen Bread",
    "Royal Chef Having A Nervous Breakdown",
    "Haunted Armor That Squeaks Constantly",
    "Guild Receptionist Demanding Paperwork",
    "Wandering Monk Dispensing Bizarre Parables",
    "Underpaid Bounty Hunter",
    "Friendly Mimic Disguised As Furniture",
    "Forest Druid Arguing With A Tree",
    "Cyberpunk Street Hacker",
    "Fallen Demigod Working Retail",
]

NPC_DEFAULT_LINES = [
    "Greetings, traveler. I used to be an adventurer like you, then I took a rogue Discord ping to the knee.",
    "Khajiit has wares if you have coin, traveler. But strictly no refunds on enchanted discord bots.",
    "Stop right there, criminal scum! Nobody breaks server etiquette on my watch!",
    "Ah, another weary soul wandering the digital realm. Care to hear a tale of ancient lore?",
    "Psst! Hey you. Don't look now, but the guild master has been watching you from the shadows.",
    "By the nine divines! How did you bypass the captcha gate without magical wards?",
    "Need something forged? I can temper your blade, but don't ask me to fix your broken sleep schedule.",
    "You have the look of someone who has stared into an error console for 14 hours straight.",
    "Stay awhile and listen! The prophecy spoke of a lurker who would rise to claim the voice channels.",
    "Careful in the dark woods ahead... the moderators lurk among the pines with banhammers raised.",
    "I trade in rare relics: half-eaten sandwiches, rusty daggers, and obsolete Discord nitro codes.",
    "My back aches, my potions are boiling over, and travelers keep asking for legendary loot for 2 copper coins.",
    "Did you hear? The dungeon boss got nerfed in the latest patch. Even a level 3 bard could take him now.",
    "Hold, stranger! Answer me this riddle: what has keys but opens no doors? ...A piano, now pay the toll.",
    "I took an oath of silence forty years ago, but frankly, you look like you need someone to complain to.",
    "Beware the mimicked chests in the deep vaults! If the treasure chest winks at you, hit it with a shovel.",
    "You look like you're carrying 400 wheels of cheese in your inventory. How are your pockets this deep?",
    "A fine day for questing! Unless of course the server host goes down for emergency maintenance.",
    "I can enchant your armor with +5 Charisma, but your social anxiety will still remain at maximum.",
    "Looking for the tavern? Follow the sound of broken tankards and bards singing off-key sea shanties.",
    "They say deep beneath the server racks, an ancient sleeping AI dreams of electric sheep.",
    "Halt! State your business in this channel, or prepare to be challenged to an honor duel of Rock-Paper-Scissors.",
    "I have traveled across seven realms, and everywhere I go, people are still arguing over pineapple on pizza.",
    "Buy a health potion, traveler! One sip cures poison, fatigue, and regret from late-night drunk texts.",
    "The stars whisper strange prophecies tonight... they say you will soon click an unknown link.",
    "Look upon my inventory and weep: fine iron blades, enchanted rings, and exactly three loose paperclips.",
    "I used to wield the legendary Banhammer, until the elders deemed my reflexes too reckless for peace.",
    "Adventurer! A goblin stole my favorite tea kettle and ran into the catacombs. Retrieve it for 50 gold!",
    "My broom cleans itself, my cauldron stirs itself, yet somehow my laundry is still piled to the ceiling.",
    "Don't mind the skeleton in the corner; he's just waiting for his Discord appeal ticket to be reviewed.",
    "You carry a heavy aura, wanderer. Sit by the hearth, eat some stew, and tell us of the outside world.",
    "Is it true what they say? In the mortal world, do humans truly communicate using glowing hand rectangles?",
    "May your blade stay sharp, your potions stay sweet, and your internet ping stay under 30 milliseconds.",
    "A curse upon the rat that gnawed through my spellbook! Now half my fireballs turn into wet cabbage.",
    "Do you ever feel like our lives are just lines of text running inside a digital simulation? ...Anyway, 5 gold for bread.",
    "I foresee great triumph in your future... followed immediately by tripping over your own shoelaces.",
    "Never trust a rogue who winks with both eyes at the same time. That's just someone with a nervous tic.",
    "The ancient gods have abandoned this temple, but the Wi-Fi signal is surprisingly strong near the altar.",
    "I once fought a dragon with nothing but a rusty spoon and an impassioned monologue. I lost, obviously.",
    "Keep your wits sharp and your coinpurse tucked away; cutpurses love newcomers with shiny gear.",
    "If you seek the secret treasure, look behind the waterfall. It's always behind the waterfall.",
    "I've been standing in this exact spot for 300 years waiting for someone to press the interact button.",
    "The barkeep waters down the ale, but the bard's stories are 100% authentic pure fantasy.",
    "Take this amulet. It won't protect you from dragons, but it glows in the dark if you lose your keys.",
    "A warrior without honor is like a sword without an edge. And a warrior without coffee is completely useless.",
    "Hear ye, hear ye! By royal decree, all Discord notifications must be muted during royal banquet hours!",
    "I can tell by the cut of your armor that you spent all your gold on cosmetics and zero on actual defense.",
    "The prophecy is clear: the chosen one shall unite the voice channels and bring balance to the memes.",
    "Travel safely, brave one. May the dice roll ever in your favor and critical failures find your foes.",
    "Walk with the wind, traveler. And remember: never fight an angry goose without a heavy round shield.",
]

COMPLIMENTS = [
    "Your energy is genuinely contagious in the best possible way. The world is significantly brighter with you around.",
    "If kindness was an Olympic sport, you’d be taking home gold medals every four years without breaking a sweat.",
    "You are genuinely one of those rare people who makes every voice chat and channel 10x more comfortable to be in.",
    "Your taste in humor and music is certified elite. Never let anyone convince you otherwise.",
    "You have an incredible gift for making others feel seen, respected, and valued.",
    "You deserve that magical feeling when you flip a pillow over and both sides are cold and fresh.",
    "You are the human equivalent of finding $20 in your winter jacket pocket on a freezing cold day.",
    "If you were a Wi-Fi signal, you’d deliver 10 Gigabit speeds with zero latency everywhere on earth.",
    "The effort and heart you put into the things you care about does not go unnoticed. You're amazing.",
    "You have a laugh that could cure minor ailments and turn around anyone's bad day.",
    "Never forget that someone's day was genuinely made better recently just because you were in it.",
    "You radiate the cozy, comforting aura of hot cocoa by a fireplace while rain falls outside.",
    "You're smart, funny, and effortlessly cool. Don't let imposter syndrome lie to you for a second.",
    "Out of 8 billion people on this planet, nobody does being you better than you.",
    "Your presence alone turns an ordinary conversation into the highlight of someone's day.",
    "You have the rare kind of charisma that doesn't need to shout to command the room.",
    "Being around you is like listening to your favorite song on a scenic highway drive with the windows down.",
    "You handle difficult situations with a quiet grace that people genuinely admire and look up to.",
    "You are someone's favorite notification on their phone. Keep shining.",
    "Your brain comes up with observations that are so creative and hilarious they deserve their own book.",
    "You are a masterclass in being authentic in a world full of copycats.",
    "You give the kind of advice that people remember and cherish five years later.",
    "Your enthusiasm for the things you love is one of the most charming things about you.",
    "You are proof that genuine goodness, wit, and kindness can exist in the same person.",
    "If your personality was a season, it would be that perfect golden hour in late autumn.",
    "You have an uncanny knack for knowing exactly what to say to lift someone's spirits.",
    "The world needs more people who listen the way you listen: with true heart and patience.",
    "You are cooler than the other side of the pillow on an August night.",
    "Your creative ideas are consistently ahead of their time. Trust your instincts more.",
    "You make people feel safe to be completely themselves around you. That is a rare superpower.",
    "The aura you bring into a room is clean, positive, and instantly grounding.",
    "Someone out there has definitely smiled just thinking about a funny memory with you.",
    "You are resilient in ways that most people will never fully realize or understand. Be proud of yourself.",
    "Your sense of humor is so quick and sharp it belongs in an award-winning writers' room.",
    "You have a heart so generous that even when you have little to give, you still offer warmth.",
    "You're the kind of friend that people write songs and make movies about.",
    "You make even mundane errands feel like a fun, spontaneous adventure.",
    "Your perspective on life is refreshing, grounded, and deeply thoughtful.",
    "You deserve all the green lights, warm cookies, and good news the universe has to offer.",
    "You are loved, appreciated, and cherished way more than people probably remember to say aloud.",
    "Your curiosity and desire to learn and grow is genuinely inspiring to watch.",
    "You are the anchor that keeps conversations steady and the spark that makes them fun.",
    "You have an impeccable sense of style and personal aesthetic that is entirely your own.",
    "You bring out the absolute best version of everyone who spends time with you.",
    "If kindness had a fragrance, you would smell like fresh mountain air after a thunderstorm.",
    "You are doing much better than you give yourself credit for. Take a breath and smile.",
    "Your loyalty to the people you care about is legendary and rare as diamond.",
    "You have a soothing voice that makes listening to you talk about anything an absolute pleasure.",
    "You are that one person in the group whose absence is immediately felt when you're away.",
    "Never dim your light just because someone else forgot to bring their sunglasses.",
    "You are a five-star human being in a world of mixed reviews.",
    "Your existence makes this Discord server — and the real world — a substantially cooler place.",
    "You have a heart made of pure gold and a wit made of razor-sharp steel.",
    "You are capable of achieving far more than your doubts try to convince you of.",
    "Your smile is the kind that lights up entire photos and stays in people's memories.",
    "You deserve all the good karma, peace of mind, and happiness coming your way.",
    "You are uniquely irreplaceable. There is not a single person on Earth who could fill your shoes.",
    "Thank you for simply existing and sharing your time and energy with the world.",
    "You are an absolute legend in the making. Keep your chin up and keep moving forward.",
    "May your week be as delightful, bright, and wonderful as your spirit.",
]


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENTS V2 VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class PPView(NexoraView):
    """Components V2 Physical Metric Scanner View."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.requester = requester
        self.target = target
        self._build_card()

    def _build_card(self):
        self.clear_container()

        length = random.randint(0, 20)
        bar = "8" + ("=" * length) + "D"

        tier_title, comm_pool, aura = PP_TIERS[-1][2:]
        for low, high, t_name, comm, a_score in PP_TIERS:
            if low <= length <= high:
                tier_title, comm_pool, aura = t_name, comm, a_score
                break

        comment = random.choice(comm_pool) if isinstance(comm_pool, list) else comm_pool

        header = (
            f"# 📏 Physical Metric Evaluation\n"
            f"> Subject: {self.target.mention}\n\n"
            f"```text\n{bar}\n```"
        )
        avatar_url = str(self.target.display_avatar.url) if self.target.display_avatar else None
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        details = (
            f"### 📐 Metric Details\n"
            f"• Length: **{length} inches** ({length * 2.54:.1f} cm)\n"
            f"• Classification: **{tier_title}**\n"
            f"• Aura Impact: `{aura:+d} Aura`\n\n"
            f"### 📋 Scientific Note\n"
            f"> *\"{comment}\"*"
        )
        self.add_text(details)

        btn_reroll = discord.ui.Button(label="Measure Again", emoji="🎲", style=discord.ButtonStyle.primary)
        btn_reroll.callback = self._on_reroll

        self.add_row(btn_reroll, DismissButton(user_id=self.requester.id))
        self.add_footer("100% certified quantum fake measurement 💀")

    async def _on_reroll(self, interaction: discord.Interaction):
        self._build_card()
        await interaction.response.edit_message(view=self)


class IQView(NexoraView):
    """Components V2 Neural IQ Diagnostic View."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=PURPLE_COLOR, timeout=timeout)
        self.requester = requester
        self.target = target
        self._build_card()

    def _build_card(self):
        self.clear_container()

        iq = random.randint(15, 300)
        logic = random.randint(5, 100)
        common_sense = random.randint(5, 100)
        chaos = random.randint(10, 100)

        title, desc_pool, status = IQ_TIERS[-1][2:]
        for low, high, t_title, t_desc, t_stat in IQ_TIERS:
            if low <= iq <= high:
                title, desc_pool, status = t_title, t_desc, t_stat
                break

        desc = random.choice(desc_pool) if isinstance(desc_pool, list) else desc_pool

        header = (
            f"# 🧠 Neural Diagnostic: Official IQ Assessment\n"
            f"> Candidate: {self.target.mention} · Frequency: `{status}`\n\n"
            f"### Tested IQ Score: **{iq}**"
        )
        avatar_url = str(self.target.display_avatar.url) if self.target.display_avatar else None
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        breakdown = (
            f"### 🏷️ Classification: {title}\n\n"
            f"### 📊 Neural Breakdown\n"
            f"• Logic: `{logic}%` {progress_bar(logic, 100, 8)}\n"
            f"• Common Sense: `{common_sense}%` {progress_bar(common_sense, 100, 8)}\n"
            f"• Raw Chaos: `{chaos}%` {progress_bar(chaos, 100, 8)}\n\n"
            f"### 🔬 Medical Diagnosis\n"
            f"> *\"{desc}\"*"
        )
        self.add_text(breakdown)

        btn_retest = discord.ui.Button(label="Retest Brain", emoji="🧠", style=discord.ButtonStyle.primary)
        btn_retest.callback = self._on_retest

        self.add_row(btn_retest, DismissButton(user_id=self.requester.id))
        self.add_footer("Calculated using advanced potato-powered neural networks.")

    async def _on_retest(self, interaction: discord.Interaction):
        self._build_card()
        await interaction.response.edit_message(view=self)


class VibeView(NexoraView):
    """Components V2 Solo & Duo Vibe Matrix View."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=CYAN_COLOR, timeout=timeout)
        self.requester = requester
        self.target = target
        self._build_card()

    def _build_card(self):
        self.clear_container()

        is_duo = self.requester.id != self.target.id

        if is_duo:
            synergy = random.randint(0, 100)
            arch_title, arch_desc_pool = VIBE_DUO_ARCHETYPES[-1][2:]
            for low, high, atitle, adesc in VIBE_DUO_ARCHETYPES:
                if low <= synergy <= high:
                    arch_title, arch_desc_pool = atitle, adesc
                    break

            arch_desc = random.choice(arch_desc_pool) if isinstance(arch_desc_pool, list) else arch_desc_pool

            header = (
                f"# 💫 Duo Vibe Compatibility Matrix\n"
                f"> Frequency between {self.requester.mention} & {self.target.mention}"
            )
            avatar_url = str(self.target.display_avatar.url) if self.target.display_avatar else None
            self.add_section(header, thumbnail_url=avatar_url)
            self.add_separator(discord.SeparatorSpacing.small)

            body = (
                f"### ⚡ Synergy Level: **{synergy}% Match**\n"
                f"`{progress_bar(synergy, 100, 12)}`\n\n"
                f"### 🎭 Duo Archetype: **{arch_title}**\n"
                f"> *\"{arch_desc}\"*"
            )
            self.add_text(body)
        else:
            vibe_pct = random.randint(55, 99)
            vibe_name, vibe_desc = random.choice(VIBE_SOLO_POOL)
            sub1 = random.randint(5, 30)
            sub2 = max(1, 100 - vibe_pct - sub1)

            header = (
                f"# ✨ Daily Personal Vibe Scanner\n"
                f"> Your vibe today: **{vibe_pct}% {vibe_name.split(' ', 1)[-1]}**\n"
                f"> Subject: {self.requester.mention}"
            )
            avatar_url = str(self.requester.display_avatar.url) if self.requester.display_avatar else None
            self.add_section(header, thumbnail_url=avatar_url)
            self.add_separator(discord.SeparatorSpacing.small)

            body = (
                f"### 🔮 Dominant Frequency: **{vibe_name}** ({vibe_pct}%)\n"
                f"`{progress_bar(vibe_pct, 100, 12)}`\n"
                f"> *\"{vibe_desc}\"*\n\n"
                f"### 📊 Secondary Resonances\n"
                f"• `{sub1}%` Snack Cravings / Caffeination\n"
                f"• `{sub2}%` Unsupervised Chaos Energy"
            )
            self.add_text(body)

        btn_recalc = discord.ui.Button(label="Recalculate Vibe", emoji="🔄", style=discord.ButtonStyle.primary)
        btn_recalc.callback = self._on_recalc

        self.add_row(btn_recalc, DismissButton(user_id=self.requester.id))
        self.add_footer("Tip: Mention another user (/vibe @user) to test Duo compatibility!")

    async def _on_recalc(self, interaction: discord.Interaction):
        self._build_card()
        await interaction.response.edit_message(view=self)


class FortuneView(NexoraView):
    """Components V2 Cursed Fortune Teller View."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=PURPLE_COLOR, timeout=timeout)
        self.requester = requester
        self.target = target
        self._build_card()

    def _build_card(self):
        self.clear_container()

        prophecy, warning, charm, level = random.choice(FORTUNES)

        header = (
            f"# 🔮 The Cursed Orb of Prophecy\n"
            f"> The ancient spirits reveal an ominous omen for {self.target.mention}..."
        )
        avatar_url = str(self.target.display_avatar.url) if self.target.display_avatar else None
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        body = (
            f"### 📜 Inevitable Prophecy\n"
            f"> *\"{prophecy}\"*\n\n"
            f"### ⚠️ Survival Advisory\n"
            f"• {warning}\n\n"
            f"### 🍀 Dubious Lucky Charm\n"
            f"• {charm}\n\n"
            f"### 💀 Danger Rating: `{level}`"
        )
        self.add_text(body)

        btn_draw = discord.ui.Button(label="Another Prophecy", emoji="🔮", style=discord.ButtonStyle.primary)
        btn_draw.callback = self._on_draw

        self.add_row(btn_draw, DismissButton(user_id=self.requester.id))
        self.add_footer("Cursed fortunes are legally binding in 0 dimensions.")

    async def _on_draw(self, interaction: discord.Interaction):
        self._build_card()
        await interaction.response.edit_message(view=self)


class NPCView(NexoraView):
    """Components V2 RPG NPC Dialogue View."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        message_text: Optional[str],
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.requester = requester
        self.target = target
        self.message_text = message_text
        self.action_taken: Optional[str] = None
        self._build_card()

    def _build_card(self):
        self.clear_container()

        archetype = random.choice(NPC_ARCHETYPES)
        line = self.message_text if self.message_text else random.choice(NPC_DEFAULT_LINES)
        gold = random.randint(25, 250)
        xp = random.randint(100, 750)

        header = (
            f"# 🎮 [ ! ] Quest Available: {archetype}\n"
            f"> Speaker: {self.target.mention} *(Level {random.randint(12, 99)} NPC)*\n\n"
            f"```fix\n\"{line}\"\n```"
        )
        avatar_url = str(self.target.display_avatar.url) if self.target.display_avatar else None
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        body = (
            f"### 🎯 Quest Objective\n"
            f"Listen attentively to **{self.target.display_name}** without interrupting.\n\n"
            f"### 🎁 Rewards Upon Completion\n"
            f"• **+{xp} XP**\n"
            f"• **+{gold} Gold Coins**\n"
            f"• **1x Rusty Iron Key**"
        )
        if self.action_taken:
            body += f"\n\n### 📜 Quest Update\n{self.action_taken}"

        self.add_text(body)

        if not self.action_taken:
            btn_accept = discord.ui.Button(label="Accept Quest", emoji="⚔️", style=discord.ButtonStyle.success)
            btn_bribe = discord.ui.Button(label="Bribe (50g)", emoji="💰", style=discord.ButtonStyle.secondary)
            btn_decline = discord.ui.Button(label="Decline / Flee", emoji="🚫", style=discord.ButtonStyle.danger)

            btn_accept.callback = self._on_accept
            btn_bribe.callback = self._on_bribe
            btn_decline.callback = self._on_decline

            self.add_row(btn_accept, btn_bribe, btn_decline, DismissButton(user_id=self.requester.id))
        else:
            self.add_row(DismissButton(user_id=self.requester.id))

        self.add_footer("Interactive RPG dialogue box • Choose your response")

    async def _on_accept(self, interaction: discord.Interaction):
        self.action_taken = f"✅ **Quest Accepted by {interaction.user.mention}!**\n*May fortune favor your blade, brave adventurer!*"
        self._build_card()
        await interaction.response.edit_message(view=self)

    async def _on_bribe(self, interaction: discord.Interaction):
        self.action_taken = f"🪙 **Bribe Accepted!**\n*{self.target.display_name} pockets the coins silently: \"I saw nothing. Walk in shadows, friend.\"*"
        self._build_card()
        await interaction.response.edit_message(view=self)

    async def _on_decline(self, interaction: discord.Interaction):
        self.action_taken = f"💨 **Fled in Terror!**\n*{interaction.user.mention} sprinted away! {self.target.display_name} will remember this cowardice.*"
        self._build_card()
        await interaction.response.edit_message(view=self)


class ComplimentView(NexoraView):
    """Components V2 Wholesome Compliment View."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=PINK_COLOR, timeout=timeout)
        self.requester = requester
        self.target = target
        self._build_card()

    def _build_card(self):
        self.clear_container()

        text = random.choice(COMPLIMENTS)

        header = (
            f"# 💖 Wholesome Transmission Received\n"
            f"> Dedicated with care to {self.target.mention}\n\n"
            f"> *\"{text}\"*"
        )
        avatar_url = str(self.target.display_avatar.url) if self.target.display_avatar else None
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        self.add_text(
            f"### ✨ Aura Radiance\n"
            f"• Sent with warmth by {self.requester.mention}\n"
            f"• Remember: you are valued, respected, and make a real difference!"
        )

        btn_another = discord.ui.Button(label="Another Compliment", emoji="💖", style=discord.ButtonStyle.secondary)
        btn_another.callback = self._on_another

        self.add_row(btn_another, DismissButton(user_id=self.requester.id))
        self.add_footer("Spread kindness today • You make the world better!")

    async def _on_another(self, interaction: discord.Interaction):
        self._build_card()
        await interaction.response.edit_message(view=self)


# ══════════════════════════════════════════════════════════════════════════════
# COG IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════════════════

class Party(commands.Cog):
    """Lively social, party, and interactive entertainment commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── PP COMMAND ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="pp", description="Completely random fake measurement scanner 💀")
    @app_commands.describe(user="The user to measure (defaults to yourself)")
    async def pp(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Perform a completely random, hilarious fake measurement."""
        target = user or ctx.author
        view = PPView(bot=self.bot, requester=ctx.author, target=target)
        await send_view(ctx, view)

    # ── IQ COMMAND ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="iq", description="Neural diagnostic: Random IQ score & hilarious evaluation")
    @app_commands.describe(user="The user to evaluate (defaults to yourself)")
    async def iq(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Random IQ generator with brain tiers and diagnostic stats."""
        target = user or ctx.author
        view = IQView(bot=self.bot, requester=ctx.author, target=target)
        await send_view(ctx, view)

    # ── VIBE COMMAND ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name="vibe", description="Daily solo vibe check or Duo compatibility dynamic")
    @app_commands.describe(user="Optional user: check your duo vibe compatibility, or check solo vibe")
    async def vibe(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Vibe check solo or duo chemistry with a friend."""
        target = user or ctx.author
        view = VibeView(bot=self.bot, requester=ctx.author, target=target)
        await send_view(ctx, view)

    # ── FORTUNE COMMAND ───────────────────────────────────────────────────────

    @commands.hybrid_command(name="fortune", description="Reveals an ominous, hilarious, and cursed fortune")
    @app_commands.describe(user="Optional user to consult the cursed prophecy for")
    async def fortune(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Draw a cursed prophecy card from the crystal ball."""
        target = user or ctx.author
        view = FortuneView(bot=self.bot, requester=ctx.author, target=target)
        await send_view(ctx, view)

    # ── NPC COMMAND ───────────────────────────────────────────────────────────

    @commands.hybrid_command(name="npc", description="Transforms a user or message into an RPG NPC dialogue box")
    @app_commands.describe(
        message="The dialogue for the NPC to say (leave blank for random line)",
        user="The user to speak as the NPC (defaults to yourself)",
    )
    async def npc(
        self,
        ctx: commands.Context,
        message: Optional[str] = None,
        user: Optional[discord.Member] = None,
    ):
        """Transform into an interactive RPG NPC with dialogue choices and quests."""
        target = user or ctx.author
        view = NPCView(bot=self.bot, requester=ctx.author, target=target, message_text=message)
        await send_view(ctx, view)

    # ── COMPLIMENT COMMAND ────────────────────────────────────────────────────

    @commands.hybrid_command(name="compliment", description="Send a wholesome, heartwarming compliment to someone")
    @app_commands.describe(user="The user to compliment (defaults to yourself)")
    async def compliment(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Send a random, beautifully formatted wholesome compliment."""
        target = user or ctx.author
        view = ComplimentView(bot=self.bot, requester=ctx.author, target=target)
        await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Party(bot))
    logger.debug("Loaded Party Cog (pp, iq, vibe, fortune, npc, compliment)")
