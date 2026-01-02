#!/bin/bash
# =============================================================================
# DOPPELGANGER TRACKER - Setup Script
# =============================================================================
# Automated setup script for Docker deployment
# Usage: ./setup.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# =============================================================================
# Main Setup
# =============================================================================

print_header "Doppelganger Tracker - Setup Script"
echo ""

# Check if Docker is installed
print_info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi
print_success "Docker found: $(docker --version)"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed."
    exit 1
fi
print_success "Docker Compose found"

echo ""

# =============================================================================
# Environment File Setup
# =============================================================================

print_header "Environment Configuration"
echo ""

if [ -f .env ]; then
    print_warning ".env file already exists"
    read -p "Do you want to backup and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
        cp .env "$BACKUP_FILE"
        print_success "Backup created: $BACKUP_FILE"
    else
        print_info "Using existing .env file"
        ENV_EXISTS=true
    fi
fi

if [ -z "$ENV_EXISTS" ]; then
    print_info "Creating .env file from template..."
    cp .env.example .env

    # Generate secure password for PostgreSQL
    if command -v openssl &> /dev/null; then
        SECURE_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

        # Update .env with secure password
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/your_secure_password_here/$SECURE_PASSWORD/g" .env
        else
            # Linux
            sed -i "s/your_secure_password_here/$SECURE_PASSWORD/g" .env
        fi

        print_success ".env file created with secure PostgreSQL password"
    else
        print_warning "OpenSSL not found, using default password"
        print_warning "Please update POSTGRES_PASSWORD in .env manually"
    fi
fi

echo ""

# =============================================================================
# Telegram Configuration
# =============================================================================

print_header "Telegram API Configuration"
echo ""
print_info "Telegram collection requires API credentials"
print_info "Get them from: https://my.telegram.org/apps"
echo ""

read -p "Do you want to configure Telegram now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter Telegram API ID: " TELEGRAM_API_ID
    read -p "Enter Telegram API Hash: " TELEGRAM_API_HASH

    # Update .env file
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/TELEGRAM_API_ID=.*/TELEGRAM_API_ID=$TELEGRAM_API_ID/" .env
        sed -i '' "s/TELEGRAM_API_HASH=.*/TELEGRAM_API_HASH=$TELEGRAM_API_HASH/" .env
    else
        sed -i "s/TELEGRAM_API_ID=.*/TELEGRAM_API_ID=$TELEGRAM_API_ID/" .env
        sed -i "s/TELEGRAM_API_HASH=.*/TELEGRAM_API_HASH=$TELEGRAM_API_HASH/" .env
    fi

    print_success "Telegram credentials configured"
else
    print_warning "Skipping Telegram configuration"
    print_info "You can configure it later by editing .env"
fi

echo ""

# =============================================================================
# Directory Setup
# =============================================================================

print_header "Creating Required Directories"
echo ""

mkdir -p data logs exports/graphs exports/reports exports/data
print_success "Created data directories"

# Set permissions (only on Unix-like systems)
if [[ "$OSTYPE" != "msys" && "$OSTYPE" != "win32" ]]; then
    chmod -R 755 data logs exports
    print_success "Set directory permissions"
fi

echo ""

# =============================================================================
# Docker Build
# =============================================================================

print_header "Docker Build"
echo ""

read -p "Do you want to build Docker images now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Building Docker images (this may take several minutes)..."
    docker compose build --no-cache
    print_success "Docker images built successfully"
else
    print_warning "Skipping Docker build"
    print_info "Run 'docker compose build' manually when ready"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

print_header "Setup Complete!"
echo ""
print_success "Environment configured successfully"
echo ""
print_info "Next steps:"
echo ""
echo "  1. Review your configuration:"
echo "     ${YELLOW}cat .env${NC}"
echo ""
echo "  2. Start the services:"
echo "     ${GREEN}docker compose up -d${NC}"
echo ""
echo "  3. Check service status:"
echo "     ${GREEN}docker compose ps${NC}"
echo ""
echo "  4. View logs:"
echo "     ${GREEN}docker compose logs -f${NC}"
echo ""
echo "  5. Access the dashboard:"
echo "     ${GREEN}http://localhost:8501${NC}"
echo ""
echo "  6. Stop the services:"
echo "     ${GREEN}docker compose down${NC}"
echo ""
print_info "Additional commands:"
echo ""
echo "  • Initialize database only:"
echo "    ${YELLOW}docker compose run --rm db-init${NC}"
echo ""
echo "  • Run analyzer (with profile):"
echo "    ${YELLOW}docker compose --profile analysis up analyzer${NC}"
echo ""
echo "  • View collector logs:"
echo "    ${YELLOW}docker compose logs -f collector${NC}"
echo ""
echo "  • Execute commands in container:"
echo "    ${YELLOW}docker compose exec collector bash${NC}"
echo ""
print_header "Happy Tracking!"
