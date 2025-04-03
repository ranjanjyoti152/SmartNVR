// WebSocket communication setup
const socket = new WebSocket('ws://localhost:5000/ws'); // Update with the correct WebSocket URL

socket.onopen = function(event) {
    console.log('WebSocket connection established');
};

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // Handle incoming data (e.g., update UI)
};

socket.onclose = function(event) {
    console.log('WebSocket connection closed');
};

// Additional JavaScript functionalities can be added below
