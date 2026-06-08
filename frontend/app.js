document.addEventListener('DOMContentLoaded', () => {
    // Mode Selectors
    const modeCards = document.querySelectorAll('.mode-card');
    const welcomeText = document.getElementById('welcome-text');
    const chatInput = document.getElementById('chat-input');
    
    // Mobile Sidebar Elements
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const mobileMenuClose = document.getElementById('mobile-menu-close');
    const appSidebar = document.getElementById('app-sidebar');

    // Welcome messages and placeholders configuration for each mode
    const modeConfigs = {
        coach: {
            welcome: "Bonjour ! Je suis l'assistant **Football IQ**. Je suis configuré en **Mode Coach**. Posez-moi vos questions pour préparer des séances d'entraînement ou clarifier des consignes tactiques basées sur nos fiches RAG.",
            placeholder: "Écrivez votre consigne tactique ou question RAG ici..."
        },
        analyst: {
            welcome: "Bonjour ! Je suis l'assistant **Football IQ**. Je suis configuré en **Mode Analyste**. Demandez-moi d'analyser une structure collective, un système de jeu ou d'identifier des forces et faiblesses.",
            placeholder: "Demandez une analyse de structure ou système..."
        },
        fan: {
            welcome: "Bonjour ! Je suis l'assistant **Football IQ**. Je suis configuré en **Mode Fan**. Posez-moi une question sur le foot de manière simple, vivante et accessible !",
            placeholder: "Posez votre question de supporter..."
        }
    };

    // 1. Switch Mode Handler
    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            // Remove active class from all cards
            modeCards.forEach(c => c.classList.remove('active'));
            
            // Add active class to clicked card
            card.classList.add('active');
            
            // Get selected mode
            const mode = card.getAttribute('data-mode');
            const config = modeConfigs[mode];
            
            if (config) {
                // Animate welcome message changes
                const welcomeWrapper = document.getElementById('welcome-message-wrapper');
                if (welcomeWrapper) {
                    welcomeWrapper.style.opacity = '0';
                    welcomeWrapper.style.transform = 'translateY(5px)';
                    
                    setTimeout(() => {
                        welcomeText.innerHTML = config.welcome.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                        chatInput.placeholder = config.placeholder;
                        welcomeWrapper.style.opacity = '1';
                        welcomeWrapper.style.transform = 'translateY(0)';
                    }, 200);
                }
            }
        });
    });

    // 2. Auto-grow Textarea Input
    if (chatInput) {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = '38px'; // Reset height
            const scrollHeight = chatInput.scrollHeight;
            if (scrollHeight > 38) {
                chatInput.style.height = `${Math.min(scrollHeight, 150)}px`;
            }
        });
    }

    // 3. Mobile Menu Handlers
    if (mobileMenuToggle && appSidebar) {
        mobileMenuToggle.addEventListener('click', () => {
            appSidebar.classList.add('open');
        });
    }

    if (mobileMenuClose && appSidebar) {
        mobileMenuClose.addEventListener('click', () => {
            appSidebar.classList.remove('open');
        });
    }

    // Close sidebar on option click (mobile optimization)
    const sidebarItems = document.querySelectorAll('.sidebar-nav li, .new-chat-btn');
    sidebarItems.forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                appSidebar.classList.remove('open');
            }
        });
    });
});
