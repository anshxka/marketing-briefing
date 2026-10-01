"""The Marketing Edit - edit this file to change what the briefing covers."""
from urllib.parse import quote_plus

TITLE = "The Marketing Edit"
TAGLINE = "Your daily marketing briefing"


def gnews(query: str) -> str:
    """Google News feed for any search (India edition)."""
    return f"https://news.google.com/rss/search?q={quote_plus(query)}+when:1d&hl=en-IN&gl=IN&ceid=IN:en"


def gnews_us(query: str) -> str:
    """Google News feed for any search (US edition, for global stories)."""
    return f"https://news.google.com/rss/search?q={quote_plus(query)}+when:1d&hl=en-US&gl=US&ceid=US:en"


# key: (section name, what belongs here - the AI reads this, colour, emoji)
CATEGORIES = {
    "campaigns_brands": ("Campaigns & brand news",
        "Major ad campaigns, rebrands and new brand identities, product launches, brand collaborations, "
        "celebrity and cricketer brand ambassadors, brand controversies and backlash. Mainly Indian brands.",
        "#E8457C", "💄"),
    "ad_media": ("Advertising & media spend",
        "Ad spend and adex reports, agency wins and account moves, media buying, TV/digital/OTT/print ad market, "
        "ad platforms (Google, Meta, Amazon Ads, YouTube), agency leadership changes.",
        "#D63384", "📺"),
    "ai_martech": ("AI in marketing & martech",
        "AI tools for marketing and advertising, generative AI in creative and media, martech and adtech launches, "
        "AI features in Google/Meta ad platforms, marketing automation and measurement.",
        "#B84DB8", "✨"),
    "social_creator": ("Social, creators & culture",
        "Social platform changes (Instagram, YouTube, LinkedIn, X, ShareChat), influencer and creator economy, "
        "viral trends, moment marketing, entertainment, OTT, cricket and pop-culture marketing.",
        "#F06292", "📱"),
    "ecom_qcom": ("E-commerce, D2C & quick commerce",
        "Amazon, Flipkart, Meesho, Myntra, Nykaa, D2C brands, quick commerce (Blinkit, Zepto, Swiggy Instamart, "
        "BB Now, Flipkart Minutes), retail media, festive sales.",
        "#E57373", "🛍️"),
    "startups_fintech": ("Startups, founders & fintech",
        "Indian startup funding, IPOs, founder news and interviews, layoffs, unicorns, UPI, NPCI, payments and "
        "fintech, consumer-tech startups.",
        "#C2185B", "🚀"),
    "consumer": ("Consumer behaviour & trends",
        "How consumers shop and spend: Indian consumer trends (rural/urban demand, premiumisation, Gen Z), "
        "US consumer trends, China consumer trends, surveys and reports on consumer behaviour.",
        "#EC6FA0", "💗"),
    "global_economy": ("Global marketing & economy",
        "Global and US marketing trends, big global brand moves, and economic shifts affecting brands: "
        "inflation, tariffs, trade, currency, FMCG and auto demand, India's economy and policy.",
        "#9C4F7E", "🌍"),
    "regulation": ("Regulation & policy",
        "Rules affecting marketing and brands: data privacy (DPDP Act, GDPR, cookies), ASCI and advertising codes, "
        "dark patterns, consumer protection, influencer disclosure rules, competition (CCI), platform regulation.",
        "#8E5A8A", "⚖️"),
    "learning": ("Case studies, jobs & competitor intel",
        "Marketing case studies and campaign breakdowns, what worked and why, marketing jobs, hiring and skills "
        "in demand, CMO moves, and competitive intelligence: how rival brands position, price and spend.",
        "#DB5A8C", "📚"),
}

# (source name, feed url). Broken or slow feeds are skipped automatically.
FEEDS = [
    # Indian marketing & advertising press
    ("ET BrandEquity", "https://brandequity.economictimes.indiatimes.com/rss/topstories"),
    ("afaqs", gnews("site:afaqs.com")),
    ("exchange4media", gnews("site:exchange4media.com")),
    ("Campaign India", gnews("site:campaignindia.in")),
    ("BestMediaInfo", gnews("site:bestmediainfo.com")),
    ("Social Samosa", gnews("site:socialsamosa.com")),
    ("Storyboard18", gnews("site:storyboard18.com")),
    # Indian startups, tech & fintech
    ("Inc42", "https://inc42.com/feed/"),
    ("Entrackr", "https://entrackr.com/feed/"),
    ("YourStory", gnews("site:yourstory.com")),
    ("MediaNama", "https://www.medianama.com/feed/"),
    # Topic searches - India
    ("Ad campaigns", gnews('"ad campaign" OR "new campaign" brand India')),
    ("Rebrands & launches", gnews('rebrand OR "brand identity" OR launches brand India')),
    ("Brand controversies", gnews("brand backlash OR controversy ad India")),
    ("Brand ambassadors", gnews('"brand ambassador" OR collaboration brand India')),
    ("Quick commerce", gnews('Blinkit OR Zepto OR Instamart OR "quick commerce"')),
    ("D2C & e-commerce", gnews("D2C brand OR Flipkart OR Meesho OR Nykaa")),
    ("UPI & fintech", gnews("UPI OR NPCI OR fintech India")),
    ("Creators", gnews('influencer OR "creator economy" India')),
    ("Indian consumers", gnews('"consumer trends" OR "consumer demand" India')),
    ("Marketing regulation", gnews('ASCI OR DPDP OR "dark patterns" OR "misleading ads"')),
    ("AI in marketing", gnews("AI marketing OR advertising")),
    ("Marketing jobs & CMOs", gnews('CMO OR "marketing head" OR "marketing jobs" India')),
    # Global
    ("Marketing Dive", "https://www.marketingdive.com/feeds/news/"),
    ("Digiday", "https://digiday.com/feed/"),
    ("Ad Age", gnews_us("site:adage.com")),
    ("US consumers", gnews_us('"consumer spending" OR "consumer trends" brands')),
    ("China consumers", gnews_us("China consumer spending OR China brands")),
    ("Global economy", gnews_us("tariffs OR inflation brands advertising")),
]

HOURS_BACK = 30              # only stories from the last N hours
PER_FEED = 4                 # max stories per source (keeps every source represented)
MAX_ARTICLES = 116           # max headlines the AI chooses from
ARTICLES_PER_CATEGORY = 3    # full articles written per section
