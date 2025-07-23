# Multi-Agent Startup Advisor Frontend

This is the React frontend for the Multi-Agent Startup Advisor application.

## Features

- **Fullscreen Interface**: Beautiful black and dark purple themed UI
- **Real-time Analysis**: Submit startup ideas and get comprehensive analysis
- **Multi-Agent Results**: Display results from market research, financial analysis, product strategy, and executive summary
- **Responsive Design**: Works well on different screen sizes
- **Loading States**: Visual feedback during analysis
- **Error Handling**: Graceful error handling and display

## Getting Started

### Prerequisites

- Node.js (v14 or higher)
- npm or yarn

### Installation

1. Navigate to the frontend directory:

   ```bash
   cd frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Start the development server:

   ```bash
   npm start
   ```

4. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

### Backend Integration

The frontend is configured to proxy API requests to the backend running on `http://localhost:8000`. Make sure your FastAPI backend is running before using the frontend.

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm build` - Builds the app for production
- `npm test` - Launches the test runner
- `npm eject` - Ejects from Create React App (one-way operation)

## Design

The application features:

- **Black and dark purple gradient background**
- **Glowing purple accents and borders**
- **Responsive layout with input section and results section**
- **Animated loading spinners**
- **Smooth hover effects and transitions**
- **Custom scrollbars**
- **Color-coded verdict badges (green for viable, red for not viable, yellow for uncertain)**
