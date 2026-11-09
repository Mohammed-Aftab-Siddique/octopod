import { expect, test, type Page } from "@playwright/test";

const now = new Date();
const currentMonthLabel = new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
}).format(now);
const currentMonthFile = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

async function login(page: Page, identifier: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email or employee ID").fill(identifier);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "My roster" })).toBeVisible();
}

test("employee can look up their ID and view the published roster", async ({ page }) => {
  await page.goto("/lookup");
  await page.getByLabel("Employee ID").fill("EMP001");
  await page.getByRole("button", { name: "Look up employee" }).click();
  await expect(page.getByText("Atharv Prawal")).toBeVisible();
  await page.getByRole("button", { name: /Continue to sign in/ }).click();

  await expect(page.getByLabel("Email or employee ID")).toHaveValue("EMP001");
  await page.getByLabel("Password", { exact: true }).fill("Employee123!");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("heading", { name: "My roster" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: /Atharv Prawal/ }).first()).toBeVisible();
  await expect(page.getByText("Published").first()).toBeVisible();

  await page.getByRole("button", { name: /Full team/ }).click();
  await expect(page.getByText("Zainab").first()).toBeVisible();
});

test("roster grid is usable on the current viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile-only layout check");

  await login(page, "EMP001", "Employee123!");
  const grid = page.getByRole("table", { name: /roster for/i });
  await expect(grid).toBeVisible();
  await expect(page.getByRole("button", { name: /Full team/ })).toBeVisible();
});

test("admin can create an employee", async ({ page }) => {
  await login(page, "admin@example.com", "Admin123!");
  await page.getByRole("link", { name: "Employees" }).click();
  await expect(page.getByRole("heading", { name: "Employees" })).toBeVisible();

  const code = `E2E${Date.now().toString().slice(-6)}`;
  const name = `End To End ${code}`;
  await page.getByRole("button", { name: /Add employee/ }).click();
  await page.getByLabel("Employee ID").fill(code);
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email").fill(`${code.toLowerCase()}@example.com`);
  await page.getByRole("button", { name: "Add employee" }).last().click();

  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await expect(page.getByText(code, { exact: true })).toBeVisible();
});

test("admin can open the published roster and export a PNG", async ({ page }) => {
  await login(page, "admin@example.com", "Admin123!");
  await page.goto("/admin/rosters");
  await page.getByRole("button", { name: "Open" }).first().click();

  await expect(
    page.getByRole("heading", { name: `${currentMonthLabel} roster` }),
  ).toBeVisible();
  await expect(page.getByText("This version is read-only")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export PNG/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(
    new RegExp(`roster-${currentMonthFile}-v\\d+\\.png`),
  );
});

test("admin can view and update roster settings", async ({ page }) => {
  await login(page, "admin@example.com", "Admin123!");
  await page.getByRole("link", { name: "Settings" }).click();

  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText("Staffing requirements")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Status legend" })).toBeVisible();

  const mondayGeneral = page.getByLabel("Monday General shift required count");
  await expect(mondayGeneral).toHaveValue(/\d+/);
  await mondayGeneral.fill("5");
  await page.getByRole("button", { name: "Save" }).click({ force: true });
  await expect(page.getByRole("button", { name: "Save" })).toBeEnabled();
});
