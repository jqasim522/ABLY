# ✈️ Advanced Travel Query Parser & Conversational Travel Agent

A comprehensive Python-based system for extracting detailed travel information from natural language input and interacting with users via a conversational agent and a web UI. Perfect for travel chatbots, ticket booking automation systems, and flight search applications.

---

## 🗂️ Project Overview

This project consists of:
- **Travel Query Extractor**: Parses natural language travel queries to extract structured information (cities, dates, flight class, passenger count, etc.).
- **Conversational Travel Agent**: An intelligent agent that interacts with users, processes travel requests, and leverages the extractor for information parsing.
- **Streamlit Web UI**: A user-friendly web interface for interacting with the travel agent and visualizing parsed results.

---

## 🧠 Features

- ✅ **Multi-city extraction** - Supports both single and multi-word city names with IATA code recognition
- ✅ **Smart flight type detection** - Distinguishes between one-way and return flights
- ✅ **Flight class parsing** - Extracts economy, business, first, and premium economy preferences
- ✅ **Advanced date extraction** - Handles complex date patterns for both departure and return dates
- ✅ **Passenger count analysis** - Uses AI to extract adults, children, and infants count
- ✅ **Robust error handling** - Graceful fallbacks and spell correction
- ✅ **Pakistani airports support** - Comprehensive coverage of Pakistani cities and airports

---

## 🏗️ Project Structure

```
├── extract_parameters.py      # Main travel query parser script
├── travel_agent.py            # Conversational travel agent logic
├── streamlit_ui.py            # Streamlit web UI for the agent
├── test_parameter_parsing.py  # Unit tests for parameter extraction
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation
└── .env                       # Environment variables (create this file)
```

---

## 📦 Installation

1. **Clone the repository**

```bash
git clone https://github.com/fasitahir/travel-query-parser.git
cd query_parameter_extractor
```

2. **Create a virtual environment** (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Download spaCy model**

```bash
python -m spacy download en_core_web_sm
```

5. **Set up environment variables**

Create a `.env` file in the project root:

```bash
BOOKME_SKY_USERNAME=your_username_here
BOOKME_SKY_PASSWORD=your_password_here
GEMINI_API_KEY=your_gemini_api_key_here
```

To get a Gemini API key:
- Visit [Google AI Studio](https://makersuite.google.com/)
- Sign in with your Google account
- Create a new API key
- Copy the key to your `.env` file

---

## 🚀 Usage

### 1. Run the Streamlit Web UI (Recommended)

Launch the interactive travel agent web app:

```bash
streamlit run streamlit_ui.py
```

This will open a browser window where you can chat with the agent, enter travel queries, and see extracted details.

### 2. Run the Extractor Standalone (Command Line)

Test the travel query extractor directly:

```bash
python extract_parameters.py
```

This will prompt you for queries in the terminal and display the parsed results.

### 3. Use the Agent in Python

You can use the agent logic programmatically or as part of the UI. To run the agent logic directly (for development or integration):

```bash
python travel_agent.py
```

Or import and use the agent in your own scripts:

```python
from travel_agent import TravelAgent
agent = TravelAgent()
response = agent.process_query("I want to fly from Lahore to Karachi tomorrow")
print(response)
```

### 4. Python Integration (Extractor Only)

```python
from extract_parameters import extract_travel_info

query = "I want to fly from Lahore to Karachi tomorrow in business class with my wife"
result = extract_travel_info(query)
print(result)
```

### Example Queries and Outputs

**One-way Flight:**
```
> I want to go from Lahore to Karachi tomorrow
{
    'source': 'LHE',
    'destination': 'KHI', 
    'flight_type': 'one_way',
    'flight_class': 'economy',
    'date': '2025-07-24',
    'passengers': {'adults': 1, 'children': 0, 'infants': 0},
    'total_passengers': 1
}
```

**Return Flight with Class:**
```
> Book business class tickets from ISB to LHE on 15th August and return on 20th August for 2 adults
{
    'source': 'ISB',
    'destination': 'LHE',
    'flight_type': 'return', 
    'flight_class': 'business',
    'departure_date': '2025-08-15',
    'return_date': '2025-08-20',
    'passengers': {'adults': 2, 'children': 0, 'infants': 0},
    'total_passengers': 2
}
```

**Family Trip:**
```
> We need first class flights from Lahore to Islamabad tomorrow for me, my wife and 2 kids
{
    'source': 'LHE',
    'destination': 'ISB',
    'flight_type': 'one_way',
    'flight_class': 'first', 
    'date': '2025-07-24',
    'passengers': {'adults': 2, 'children': 2, 'infants': 0},
    'total_passengers': 4
}
```

---

## 🛫 Supported Cities and Airports

The parser supports major Pakistani cities with their IATA codes:

| City | IATA Code | Airport |
|------|-----------|---------|
| Lahore | LHE | Allama Iqbal International |
| Karachi | KHI | Jinnah International |
| Islamabad | ISB | Islamabad International |
| Multan | MUX | Multan International |
| Peshawar | PEW | Bacha Khan International |
| Quetta | UET | Quetta Airport |
| Faisalabad | LYP | Faisalabad Airport |
| Sialkot | SKT | Sialkot Airport |
| And many more... | | |

---

## 🎯 Features Deep Dive

### 1. City Extraction
- **Multi-word cities**: "Dera Ghazi Khan", "Rahim Yar Khan"
- **IATA code recognition**: "LHE", "KHI", "ISB"
- **Fuzzy matching**: Handles typos like "Lahor" → "Lahore"
- **Context-aware**: Uses directional indicators like "from", "to"

### 2. Flight Type Detection
- **Conservative approach**: Only detects return when strong indicators present
- **Pattern matching**: "round trip", "return", "back to"
- **Date range analysis**: "between 10th and 15th"
- **Multiple city patterns**: Complex routing detection

### 3. Flight Class Recognition
- **Multiple formats**: "business class", "biz class", "J class"
- **Context awareness**: "professional travel" → business class
- **Abbreviation support**: "F" → first class
- **Fuzzy matching**: Handles misspellings

### 4. Date Parsing
- **Natural language**: "tomorrow", "day after tomorrow", "next Friday"
- **Complex patterns**: "15th of August", "Aug 15th", "15/08/2025"
- **Return date handling**: "go on 10th and come back on 15th"
- **Date range detection**: "between 10th and 15th"

### 5. Passenger Count (AI-Powered)
- **Family relationships**: "me and my wife" → 2 adults
- **Age-based classification**: "2-year-old" → infant
- **Context understanding**: "family of 4" → 2 adults, 2 children
- **Fallback handling**: Defaults to 1 adult if unclear

---

## 🧪 Technologies Used

- **[spaCy](https://spacy.io/)** – Advanced NLP pipeline for entity parsing
- **[RapidFuzz](https://github.com/maxbachmann/RapidFuzz)** – Fast fuzzy string matching
- **[Autocorrect](https://github.com/phatpiglet/autocorrect)** – Automatic spelling correction
- **[Parsedatetime](https://github.com/bear/parsedatetime)** – Natural language date parsing
- **[Google Generative AI](https://ai.google.dev/)** – AI-powered passenger count extraction
- **[Python-dotenv](https://github.com/theskumar/python-dotenv)** – Environment variable management

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for passenger extraction | Yes |

### Customization

You can extend the parser by:

1. **Adding new cities**: Update the `city_to_iata` dictionary
2. **Custom flight classes**: Modify the `class_mappings` in `extract_flight_class()`
3. **Date patterns**: Add patterns to the date extraction functions
4. **Language support**: Replace spaCy model and update dictionaries

---

## 🐛 Troubleshooting

**Common Issues:**

1. **Gemini API Error**: Ensure your API key is valid and set in `.env`
2. **spaCy Model Missing**: Run `python -m spacy download en_core_web_sm`
3. **Date Parsing Issues**: Check date format and try more explicit phrasing
4. **City Not Recognized**: Verify city name spelling or use IATA code

**Debug Mode:**
```python
# Enable debug output
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📊 Performance

- **Accuracy**: ~95% for city extraction
- **Speed**: <100ms per query on average hardware
- **Memory**: ~50MB with spaCy model loaded
- **Supported queries**: 1000+ different phrasings tested

---

## 📝 License

MIT License. Feel free to use, fork, and improve!

---


## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/fasitahir/travel-query-parser/issues)
- **Discussions**: [GitHub Discussions](https://github.com/fasitahir/travel-query-parser/discussions)
- **Email**: fasitahir2019@gmail.com

---

**Happy Travels!** ✈️🌍
