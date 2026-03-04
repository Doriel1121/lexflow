@echo off
echo Installing Frontend Test Dependencies...
echo.

cd frontend

echo Installing testing libraries...
call npm install --save-dev @testing-library/react@^14.1.2
call npm install --save-dev @testing-library/jest-dom@^6.1.5
call npm install --save-dev @testing-library/user-event@^14.5.1
call npm install --save-dev vitest@^1.0.4
call npm install --save-dev jsdom@^23.0.1
call npm install --save-dev @vitest/ui@^1.0.4

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Run tests with: npm test
echo Run tests with UI: npm run test:ui
echo.
