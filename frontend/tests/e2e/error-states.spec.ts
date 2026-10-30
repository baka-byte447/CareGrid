import { test, expect } from '@playwright/test';

test.describe('Error and Resilience States', () => {
  test('handles network failure with informative error state and retry action', async ({ page }) => {
    // Intercept /api/patients and force network failure
    await page.route('**/api/patients', (route) => route.abort());

    await page.goto('/queue');

    // Error state alert should be displayed
    const alert = page.locator('[role="alert"]');
    await expect(alert).toBeVisible();
    await expect(page.locator('button:has-text("Retry Connection")')).toBeVisible();
  });

  test('admin portal explicitly communicates missing backend endpoints with disabled buttons', async ({ page }) => {
    await page.goto('/admin');

    await expect(page.locator('h1:has-text("Hospital Administration & Configuration")')).toBeVisible();
    await expect(page.locator('text=Required Backend Administrative Endpoints')).toBeVisible();

    // Configure buttons must be disabled
    const configBtn = page.locator('button:has-text("Configure")').first();
    await expect(configBtn).toBeDisabled();
  });

  test('login route respects VITE_AUTH_ENABLED flag', async ({ page }) => {
    await page.goto('/login');

    // With VITE_AUTH_ENABLED=false, displays open access clinical environment banner
    await expect(page.locator('text=Open Access Clinical Environment')).toBeVisible();
    await expect(page.locator('button:has-text("Enter Hospital Command Centre")')).toBeVisible();
  });
});
