// Create an object to send as JSON
const dataToSend = {
  query: 'Who are you?',
};

// Make a POST request with fetch
fetch('http://127.0.0.1:8000/submit', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(dataToSend)
})
.then(response => {
  // Handle response
  if (response.ok) {
    return response.json(); // Parse JSON response
  }
  throw new Error('Network response was not ok.');
})
.then(jsonResponse => {
  // Handle JSON response
  console.log(jsonResponse);
})
.catch(error => {
  // Handle errors
  console.error('There was a problem with the fetch operation:', error);
});
