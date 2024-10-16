// testClient.js
const io = require('socket.io-client');

const socket = io('http://localhost:3336');

socket.on('connect', () => {
  console.log('Connected to backend');

  socket.on('boat_locations', (data) => {
    console.log('Received boat_locations:', data);
  });
});

socket.on('disconnect', () => {
  console.log('Disconnected from backend');
});
