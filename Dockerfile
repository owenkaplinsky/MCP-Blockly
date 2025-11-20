# Base image
FROM python:3.11-slim

# Install Node.js and npm
RUN apt-get update && apt-get install -y nodejs npm

# Copy entire repo into container
WORKDIR /app
COPY . .

# Install Python dependencies (if any)
RUN pip install -r requirements.txt || true

# Change working directory to the project folder for Node commands
WORKDIR /app/project

# Install Node dependencies
RUN npm install

# Build frontend
RUN npm run build

# Expose the port your app uses (usually 7860 or 8080)
EXPOSE 7860

# Start the app (npm start inside project)
CMD ["npm", "run", "start"]
