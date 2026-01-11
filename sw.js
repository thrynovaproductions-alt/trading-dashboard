// Listener for Push Events
self.addEventListener('push', function(event) {
    const data = event.data ? event.data.json() : { title: 'Market Alert', body: 'New Signal Detected!' };
    const options = {
        body: data.body,
        icon: 'https://cdn-icons-png.flaticon.com/512/2464/2464402.png',
        badge: 'https://cdn-icons-png.flaticon.com/512/2464/2464402.png'
    };
    event.waitUntil(self.registration.showNotification(data.title, options));
});
