# MultiAgent Frontend

A modern, interactive chat interface for the MultiAgent system built with Streamlit.

## Features

- Real-time chat interface
- Support for displaying tool results
- Session management
- Mobile-responsive design
- Clean, modern UI

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Node.js and npm (for development only)

## Installation

1. Clone the repository
2. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
3. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the frontend directory with the following variables:

```env
# API configuration
API_BASE_URL=http://localhost:8000  # Update if your API is hosted elsewhere

# Optional: Customize the app title and description
APP_TITLE=MultiAgent Chat
APP_DESCRIPTION="A powerful AI assistant with GitHub and API capabilities"
```

## Running the Application

1. Ensure the backend API is running
2. Start the Streamlit app:
   ```bash
   streamlit run app.py
   ```
3. Open your browser to the URL shown in the terminal (usually http://localhost:8501)

## Development

### Available Scripts

- `streamlit run app.py` - Start the development server
- `pytest` - Run tests (coming soon)

### Project Structure

```
frontend/
├── app.py                # Main Streamlit application
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── .env.example         # Example environment variables
```

## Deployment

### Local Deployment

1. Build the Docker image:
   ```bash
   docker build -t multiagent-frontend .
   ```
2. Run the container:
   ```bash
   docker run -p 8501:8501 -e API_BASE_URL=http://your-api-url multiagent-frontend
   ```

### Cloud Deployment

The application can be deployed to any cloud platform that supports Python applications, such as:

- Streamlit Cloud
- Heroku
- Google Cloud Run
- AWS Elastic Beanstalk
- Azure App Service

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
