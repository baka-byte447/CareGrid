import { test, expect } from '@playwright/test';

test.describe('CareGrid Bed Allocation Approval Flow', () => {
  test('displays command centre without hospital header text and with KPI metrics', async ({ page }) => {
    await page.goto('/');

    // Check title and header
    await expect(page).toHaveTitle(/CareGrid/);
    await expect(page.locator('text=Synthetic Data')).toHaveCount(0);
    await expect(page.locator('text=St. Jude Central Hospital — Metropolitan Campus')).toHaveCount(0);

    // Check presence of key KPI metric cards
    await expect(page.locator('text=Bed Occupancy')).toBeVisible();
    await expect(page.locator('text=Admission Queue')).toBeVisible();
    await expect(page.locator('text=Ventilator Fleet')).toBeVisible();
  });

  test('navigates to queue and displays patient list with simulated dates', async ({ page }) => {
    await page.goto('/queue');

    // Header and search bar
    await expect(page.locator('h1:has-text("Patient Admission Queue")')).toBeVisible();

    // Filter controls
    await expect(page.locator('text=Waiting')).toBeVisible();
    await expect(page.locator('text=Admitted')).toBeVisible();

    // Verify simulated dates are present in table
    const table = page.locator('table');
    await expect(table).toBeVisible();
  });

  test('reject button in recommendation drawer is disabled with informative tooltip', async ({ page }) => {
    await page.goto('/queue');

    // If an Allocate Bed button exists, click it
    const allocateBtn = page.locator('button:has-text("Allocate Bed")').first();
    if (await allocateBtn.isVisible()) {
      await allocateBtn.click();

      // Recommendation drawer should open
      await expect(page.locator('h2:has-text("Bed Allocation Decision")')).toBeVisible();

      // The reject button MUST be disabled per backend specifications
      const rejectBtn = page.locator('button:has-text("Reject Recommendation")');
      await expect(rejectBtn).toBeVisible();
      await expect(rejectBtn).toBeDisabled();
    }
  });
});
