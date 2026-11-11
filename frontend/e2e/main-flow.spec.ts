import { expect, test } from "@playwright/test";

function limaDatePlus(days: number): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  const today = new Date(Date.UTC(Number(value.year), Number(value.month) - 1, Number(value.day)));
  today.setUTCDate(today.getUTCDate() + days);
  return today.toISOString().slice(0, 10);
}

test("completes the subscription lifecycle through the web app", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Resumen" })).toBeVisible();

  await page.getByRole("link", { name: "Suscripciones" }).first().click();
  await page.getByRole("button", { name: "Nueva suscripción" }).click();
  await page.getByLabel("Nombre").fill("Internet hogar");
  await page.getByRole("spinbutton").fill("89.90");
  await page.getByLabel("Próxima fecha de cobro").fill(limaDatePlus(3));
  await page.getByRole("dialog").getByRole("button", { name: "Crear suscripción" }).click();
  await expect(page.getByRole("link", { name: "Internet hogar", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Resumen" }).first().click();
  await expect(page.getByText("Gasto mensual estimado")).toBeVisible();
  await expect(page.getByRole("link", { name: /Internet hogar/ })).toBeVisible();

  await page.getByRole("link", { name: "Suscripciones" }).first().click();
  await page.getByRole("link", { name: "Internet hogar", exact: true }).click();
  await page.getByRole("button", { name: "Confirmar cobro" }).click();
  await page.getByLabel("Importe pagado").fill("92.50");
  await page.getByRole("button", { name: "Confirmar cobro" }).last().click();
  await expect(page.getByText(/92\.50/)).toBeVisible();

  await page.reload();
  await expect(page.getByText(/pagado el/)).toBeVisible();
  await page.getByRole("button", { name: "Deshacer último" }).click();
  await page.getByRole("button", { name: "Deshacer cobro" }).click();
  await expect(page.getByText("Aún no hay pagos registrados")).toBeVisible();

  await page.getByRole("button", { name: "Editar" }).click();
  const nameInput = page.getByLabel("Nombre");
  await nameInput.fill("Internet actualizado");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(page.getByRole("heading", { name: "Internet actualizado" })).toBeVisible();

  await page.getByRole("button", { name: "Desactivar" }).click();
  await expect(page.getByText("Inactiva")).toBeVisible();
  await page.getByRole("button", { name: "Reactivar" }).click();
  const activeToggle = page.getByLabel(/Suscripción activa/);
  await page.getByText("Suscripción activa", { exact: true }).click();
  await expect(activeToggle).toBeChecked();
  const renewalDate = page.getByLabel(/Próxima fecha de cobro/);
  const reactivationDate = limaDatePlus(12);
  await renewalDate.fill(reactivationDate);
  await expect(renewalDate).toHaveValue(reactivationDate);
  await page.getByRole("dialog").getByRole("button", { name: "Guardar cambios" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByText("Activa", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Eliminar" }).click();
  await page.getByRole("button", { name: "Eliminar definitivamente" }).click();
  await expect(page.getByRole("link", { name: "Internet actualizado" })).not.toBeVisible();
});

test("serves direct browser routes and their assets from FastAPI", async ({ page }) => {
  await page.goto("/suscripciones/invalid-id");
  await expect(page.getByText("No encontramos esta suscripción.")).toBeVisible();

  const response = await page.request.get("/favicon.svg");
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).toContain("<svg");
});
