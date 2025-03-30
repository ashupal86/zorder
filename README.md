# Digital Waiter - AI-Powered Restaurant Management System

Digital Waiter is a modern, AI-powered web application that revolutionizes restaurant operations by automating menu management, order processing, and customer service. Built with Flask and Bootstrap, it provides a seamless experience for both restaurant staff and customers.

## Features

### 🤖 AI-Powered Menu Management
- Automatic menu extraction from images/PDFs using OCR
- Smart menu categorization and formatting
- Real-time menu updates and availability management
- Image recognition for menu items

### 📱 QR-Based Contactless Ordering
- Unique QR codes for each table
- Mobile-friendly digital menu
- Smart dish recommendations
- Real-time order tracking

### 🔄 Intelligent Order Management
- Automated order processing
- Smart preparation time estimation
- Kitchen load optimization
- Real-time status updates

### 💳 Automated Billing & Payments
- Integrated payment processing
- Multiple payment options
- Automatic tax calculation
- Digital receipts

### 📊 Analytics & Insights
- Sales analytics
- Popular items tracking
- Peak hours analysis
- Customer feedback analytics

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Bootstrap 5
- **Database**: PostgreSQL
- **AI Components**:
  - OCR: Tesseract
  - NLP: Google Gemini
  - Machine Learning: scikit-learn
- **Additional Features**:
  - QR Code Generation
  - Real-time Notifications
  - Dark Mode Support

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/digital-waiter.git
cd digital-waiter
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Create .env file
cp .env.example .env

# Edit .env with your configurations:
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://username:password@localhost/digital_waiter
GEMINI_API_KEY=your-gemini-api-key
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
flask run
```

The application will be available at `http://localhost:5000`

## Configuration

### Database Setup
1. Install PostgreSQL
2. Create a new database:
```sql
CREATE DATABASE digital_waiter;
```
3. Update the `DATABASE_URL` in your `.env` file

### OCR Setup
1. Install Tesseract OCR:
   - Windows: Download installer from GitHub
   - Linux: `sudo apt-get install tesseract-ocr`
   - macOS: `brew install tesseract`

2. Verify installation:
```bash
tesseract --version
```

## Usage

### Restaurant Setup
1. Register your restaurant
2. Upload your existing menu
3. Configure tables and generate QR codes
4. Customize menu categories and items

### Customer Ordering
1. Scan table QR code
2. Browse digital menu
3. Add items to cart
4. Place order and pay

### Order Management
1. Monitor incoming orders
2. Track preparation status
3. Process payments
4. Collect feedback

## Development

### Project Structure
```
digital_waiter/
├── app.py              # Main application file
├── models.py           # Database models
├── routes/            
│   ├── auth.py        # Authentication routes
│   ├── menu.py        # Menu management
│   ├── orders.py      # Order processing
│   └── admin.py       # Admin dashboard
├── static/
│   ├── css/           # Stylesheets
│   ├── js/            # JavaScript files
│   └── img/           # Images and uploads
├── templates/
│   ├── auth/          # Authentication templates
│   ├── menu/          # Menu templates
│   └── admin/         # Dashboard templates
└── requirements.txt    # Dependencies
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Security

- All passwords are hashed using secure algorithms
- Payment information is handled securely
- API keys and sensitive data are stored in environment variables
- CSRF protection is enabled
- Input validation and sanitization

## Support

For support and questions:
- Create an issue on GitHub
- Contact: support@digitalwaiter.com
- Documentation: [docs.digitalwaiter.com](https://docs.digitalwaiter.com)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Google Gemini for NLP capabilities
- Tesseract OCR team
- Flask and Bootstrap communities
- All contributors and users 