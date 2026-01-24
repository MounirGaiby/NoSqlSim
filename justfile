# NoSqlSim Justfile
# Cross-platform task runner for development, testing, and deployment

# Default recipe - show help
default:
    @just --list

# ============================================
# SETUP COMMANDS
# ============================================

# Install all dependencies (frontend + backend)
setup:
    @echo "Setting up NoSqlSim..."
    @just setup-backend
    @just setup-frontend
    @echo ""
    @echo "Setup complete! Run 'just start' to begin."

# Setup backend dependencies
setup-backend:
    @echo "Installing backend dependencies..."
    cd backend && pip install -r requirements.txt

# Setup frontend dependencies
setup-frontend:
    @echo "Installing frontend dependencies..."
    cd frontend && pnpm install

# ============================================
# START/STOP COMMANDS
# ============================================

# Start both backend and frontend (background)
start:
    @echo "Starting NoSqlSim..."
    @just start-backend &
    @sleep 2
    @just start-frontend &
    @echo ""
    @echo "NoSqlSim is starting..."
    @echo "  Backend:  http://localhost:8000"
    @echo "  Frontend: http://localhost:5173"
    @echo ""
    @echo "Run 'just logs' to view backend logs"
    @echo "Run 'just stop' to stop all services"

# Start backend server
backend:
    cd backend && python -m app.main

# Start backend in background with log file
start-backend:
    @mkdir -p .logs
    @echo "Starting backend server..."
    cd backend && python -m app.main > ../.logs/backend.log 2>&1 &
    @echo "Backend started (PID saved, logs at .logs/backend.log)"

# Start frontend dev server
frontend:
    cd frontend && pnpm dev

# Start frontend in background
start-frontend:
    @mkdir -p .logs
    @echo "Starting frontend dev server..."
    cd frontend && pnpm dev > ../.logs/frontend.log 2>&1 &
    @echo "Frontend started (logs at .logs/frontend.log)"

# Stop all services
stop:
    @echo "Stopping all NoSqlSim services..."
    -pkill -f "python -m app.main" 2>/dev/null || true
    -pkill -f "vite" 2>/dev/null || true
    @echo "All services stopped."

# ============================================
# LOGS COMMANDS
# ============================================

# View backend logs (follow mode)
logs:
    @if [ -f .logs/backend.log ]; then \
        tail -f .logs/backend.log; \
    else \
        echo "No log file found. Start the backend first with 'just start'"; \
    fi

# View frontend logs
logs-frontend:
    @if [ -f .logs/frontend.log ]; then \
        tail -f .logs/frontend.log; \
    else \
        echo "No log file found. Start the frontend first with 'just start'"; \
    fi

# View all logs
logs-all:
    @if [ -f .logs/backend.log ] && [ -f .logs/frontend.log ]; then \
        tail -f .logs/backend.log .logs/frontend.log; \
    else \
        echo "Log files not found. Start services first with 'just start'"; \
    fi

# Clear all logs
logs-clear:
    @rm -rf .logs
    @echo "Logs cleared."

# ============================================
# TEST COMMANDS
# ============================================

# Run integration tests
test:
    @echo "Running integration tests..."
    cd backend && python -m pytest tests/integration/ -v --tb=short

# Run integration tests with full output
test-verbose:
    @echo "Running integration tests (verbose)..."
    cd backend && python -m pytest tests/integration/ -v -s --tb=long

# Run unit tests only
test-unit:
    @echo "Running unit tests..."
    cd backend && python -m pytest tests/unit/ -v --tb=short

# Run all tests
test-all:
    @echo "Running all tests..."
    cd backend && python -m pytest tests/ -v --tb=short

# ============================================
# CLEAN COMMANDS
# ============================================

# Clean everything (containers, logs, temp files)
clean:
    @echo "Cleaning up NoSqlSim..."
    @just stop
    @just clean-containers
    @just clean-logs
    @just clean-pycache
    @echo "Cleanup complete!"

# Remove all MongoDB containers and networks created by NoSqlSim
clean-containers:
    @echo "Removing NoSqlSim Docker containers..."
    -docker ps -a --filter "name=nosqlsim" -q | xargs -r docker rm -f 2>/dev/null || true
    -docker ps -a --filter "name=mongo-rs" -q | xargs -r docker rm -f 2>/dev/null || true
    @echo "Removing NoSqlSim Docker networks..."
    -docker network ls --filter "name=nosqlsim" -q | xargs -r docker network rm 2>/dev/null || true
    @echo "Containers and networks cleaned."

# Remove log files
clean-logs:
    @rm -rf .logs
    @echo "Logs cleaned."

# Remove Python cache files
clean-pycache:
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    @echo "Python cache cleaned."

# Remove Nix/direnv files (reset to manual setup)
clean-nix:
    @echo "Removing Nix/direnv configuration..."
    @rm -rf .direnv
    @echo "Nix environment cache cleaned."
    @echo "To fully reset, also delete flake.lock if present."

# Full reset - removes everything including node_modules and venv
clean-full:
    @just clean
    @echo "Removing node_modules..."
    @rm -rf frontend/node_modules
    @echo "Removing Python venv..."
    @rm -rf backend/venv
    @rm -rf .direnv
    @rm -f flake.lock
    @echo "Full cleanup complete. Run 'just setup' to reinstall."

# ============================================
# DOCKER COMMANDS (Full App in Container)
# ============================================

# Build Docker images for the full app
docker-build:
    @echo "Building NoSqlSim Docker images..."
    docker-compose -f docker/docker-compose.app.yml build

# Run the full app in Docker
docker-up:
    @echo "Starting NoSqlSim in Docker..."
    docker-compose -f docker/docker-compose.app.yml up -d
    @echo ""
    @echo "NoSqlSim is running in Docker!"
    @echo "  Frontend: http://localhost:3000"
    @echo "  Backend:  http://localhost:8000"

# Stop Docker app
docker-down:
    @echo "Stopping NoSqlSim Docker containers..."
    docker-compose -f docker/docker-compose.app.yml down

# View Docker logs
docker-logs:
    docker-compose -f docker/docker-compose.app.yml logs -f

# ============================================
# DEVELOPMENT HELPERS
# ============================================

# Format Python code
fmt:
    @echo "Formatting Python code..."
    cd backend && python -m black . 2>/dev/null || echo "black not installed, skipping..."

# Lint frontend code
lint:
    @echo "Linting frontend..."
    cd frontend && pnpm lint

# Build frontend for production
build:
    @echo "Building frontend..."
    cd frontend && pnpm build

# Check if Docker is running
check-docker:
    @docker info > /dev/null 2>&1 && echo "Docker is running" || echo "Docker is NOT running - please start Docker Desktop"

# Show system status
status:
    @echo "=== NoSqlSim Status ==="
    @echo ""
    @echo "Docker:"
    @docker info > /dev/null 2>&1 && echo "  Status: Running" || echo "  Status: NOT RUNNING"
    @echo "  Containers: $(docker ps -a --filter 'name=nosqlsim' -q | wc -l | tr -d ' ') nosqlsim containers"
    @echo "  Networks: $(docker network ls --filter 'name=nosqlsim' -q | wc -l | tr -d ' ') nosqlsim networks"
    @echo ""
    @echo "Services:"
    @pgrep -f "python -m app.main" > /dev/null && echo "  Backend: Running" || echo "  Backend: Stopped"
    @pgrep -f "vite" > /dev/null && echo "  Frontend: Running" || echo "  Frontend: Stopped"
