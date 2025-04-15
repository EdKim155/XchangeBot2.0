document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const calculatorForm = document.getElementById('calculator-form');
    const queryInput = document.getElementById('query-input');
    const exampleButtons = document.querySelectorAll('.example-btn');
    
    // Function to add a new message to the chat
    function addMessage(content, type = 'bot') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Check if content has line breaks and format accordingly
        if (content.includes('\n')) {
            // For multiline content, use pre-formatted text
            const pre = document.createElement('pre');
            pre.className = 'm-0';
            pre.textContent = content;
            messageContent.appendChild(pre);
        } else {
            // For single line content
            messageContent.textContent = content;
        }
        
        messageDiv.appendChild(messageContent);
        chatContainer.appendChild(messageDiv);
        
        // Scroll to the bottom of the chat
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Handle form submission
    calculatorForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const query = queryInput.value.trim();
        if (!query) return;
        
        // Add user message
        addMessage(query, 'user');
        
        // Clear input
        queryInput.value = '';
        
        // Show loading state
        const loadingId = setTimeout(() => {
            addMessage('Computing...', 'bot');
            chatContainer.lastChild.id = 'loading-message';
        }, 300);
        
        // Send request to the server
        fetch('/calculate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query }),
        })
        .then(response => response.json())
        .then(data => {
            clearTimeout(loadingId);
            
            // Remove loading message if it exists
            const loadingMessage = document.getElementById('loading-message');
            if (loadingMessage) {
                loadingMessage.remove();
            }
            
            // Add bot response
            if (data.error) {
                addMessage(`Error: ${data.error}`, 'bot');
            } else {
                addMessage(data.result, 'bot');
            }
        })
        .catch(error => {
            clearTimeout(loadingId);
            
            // Remove loading message if it exists
            const loadingMessage = document.getElementById('loading-message');
            if (loadingMessage) {
                loadingMessage.remove();
            }
            
            addMessage(`Sorry, there was an error processing your request: ${error.message}`, 'bot');
        });
    });
    
    // Handle example button clicks
    exampleButtons.forEach(button => {
        button.addEventListener('click', function() {
            queryInput.value = this.textContent;
            queryInput.focus();
        });
    });
    
    // Focus on input when the page loads
    queryInput.focus();
});
