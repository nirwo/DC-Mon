# Data Center Monitor (DC-Mon)

A modern web application for monitoring and managing data center systems, built with FastAPI, Vue.js, and Tailwind CSS.

## Features

- 📊 **Status Overview**: Real-time monitoring of all systems
- 👥 **Owner Management**: Track system owners and their contact information
- 🌓 **Dark Mode**: Comfortable viewing in any environment
- 📱 **Responsive Design**: Works on desktop and mobile devices

## Prerequisites

- Python 3.8 or higher
- Node.js 16.x or higher
- npm or yarn

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd datacenter-shutdown-manager
   ```

2. **Set up the Backend**
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   
   # Install Python dependencies
   cd backend
   pip install -r requirements.txt
   ```

3. **Set up the Frontend**
   ```bash
   # Install Node.js dependencies
   cd frontend
   npm install
   ```

## Running the Application

1. **Start the Backend Server**
   ```bash
   # From the backend directory
   uvicorn main:app --reload --port 3000
   ```
   The API will be available at `http://localhost:3000`

2. **Start the Frontend Development Server**
   ```bash
   # From the frontend directory
   npm run dev
   ```
   The web interface will be available at `http://localhost:3001`

3. **Using the Start Script**
   ```bash
   # From the project root
   chmod +x start.sh  # Make the script executable
   ./start.sh        # Run both backend and frontend
   ```

## API Documentation

- API documentation is available at `http://localhost:3000/docs`
- ReDoc alternative documentation at `http://localhost:3000/redoc`

## Project Structure

```
datacenter-shutdown-manager/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── requirements.txt  # Python dependencies
│   └── servers.db       # SQLite database
├── frontend/
│   ├── src/
│   │   ├── styles.css   # Tailwind CSS styles
│   │   └── components/  # Vue components
│   ├── index.html       # Main HTML file
│   ├── app.js          # Vue application
│   └── package.json    # Node.js dependencies
├── start.sh           # Startup script
└── README.md         # This file
```

## Usage

1. **Status Overview Page**
   - View total number of systems
   - Monitor online/offline status
   - Check systems with issues
   - Access quick contact information

2. **Owners Page**
   - List all system owners
   - View contact details
   - See systems managed by each owner
   - Quick-access contact options

## Development

- The project uses the `modern-ui` branch for development
- Tailwind CSS v3.4.1 for styling
- Vue.js for frontend components
- FastAPI for backend API
- SQLite for data storage

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
