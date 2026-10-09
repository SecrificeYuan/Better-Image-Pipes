import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

function document(type = 'blank_image') {
  return { version: 1, name: 'C++ verification', seed: 23, iterationCount: 1,
    graph: { nodes: [{ id: '真实节点', type, params: {}, position: { x: 80, y: 80 } }], edges: [] } }
}

test('real backend export, Monaco, download, stale state and both languages', async ({ page, request }, info) => {
  const workflow = document()
  await page.addInitScript((doc) => {
    localStorage.setItem('image-pipes.language', 'en')
    localStorage.setItem('image-pipes.workflow.v1', JSON.stringify(doc))
  }, workflow)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Code', exact: true }).click()
  await page.getByRole('button', { name: 'Export Python', exact: true }).click()
  await expect(page.locator('.monaco-editor')).toBeVisible()
  const python = await request.post('/api/codegen', { data: { graph: workflow.graph, seed: 23 } })
  expect(python.ok()).toBeTruthy()
  const pythonDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download source' }).click()
  expect(await readFile(await (await pythonDownload).path() as string, 'utf8'))
    .toBe((await python.json()).code)
  await page.getByRole('button', { name: 'C++', exact: true }).click()
  const cppGrammar = page.waitForResponse((r) => /\/cpp-[^/]+\.js(?:\?|$)/.test(r.url()) && r.status() === 200)
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export C++', exact: true }).click()
  const downloaded = await pending
  expect(downloaded.suggestedFilename()).toBe('pipeline.cpp')
  const file = info.outputPath('pipeline.cpp')
  await downloaded.saveAs(file)
  const source = await readFile(file, 'utf8')
  expect(source).toContain('int main()')
  const response = await request.post('/api/codegen/cpp', {
    data: { graph: workflow.graph, seed: 23, iteration_count: 1 },
  })
  expect(response.ok()).toBeTruthy()
  expect(source).toBe((await response.json()).code)
  await expect(page.locator('.monaco-editor')).toBeVisible()
  await cppGrammar
  expect((await page.locator('.monaco-editor').boundingBox())!.height).toBeGreaterThan(80)
  await page.getByRole('spinbutton', { name: 'Seed', exact: true }).fill('24')
  await expect(page.getByRole('button', { name: 'Download source' })).toBeDisabled()
  await expect(page.getByText('Workflow changed. Generate C++ again before downloading.')).toBeVisible()
  const regenerated = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export C++', exact: true }).click()
  expect(await readFile(await (await regenerated).path() as string, 'utf8')).toContain('pipeline_seed = 24ULL')
  await page.getByRole('button', { name: /^Workflow/ }).click()
  await page.getByRole('menuitem', { name: 'Language', exact: true }).click()
  await page.getByRole('menuitem', { name: '简体中文', exact: true }).click()
  await expect(page.getByRole('button', { name: '导出 C++', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  await page.screenshot({ path: info.outputPath('cpp-zh.png') })
})

test('unsupported node returns located error and stops download', async ({ page }) => {
  await page.addInitScript((doc) => {
    localStorage.setItem('image-pipes.language', 'en')
    localStorage.setItem('image-pipes.workflow.v1', JSON.stringify(doc))
  }, document('custom_python'))
  await page.goto('/')
  await page.getByRole('tab', { name: 'Code', exact: true }).click()
  await page.getByRole('button', { name: 'C++', exact: true }).click()
  const response = page.waitForResponse((r) => r.url().endsWith('/api/codegen/cpp'))
  const downloads: string[] = []
  page.on('download', (d) => downloads.push(d.suggestedFilename()))
  await page.getByRole('button', { name: 'Export C++', exact: true }).click()
  expect((await response).status()).toBe(422)
  await expect(page.getByRole('alert').filter({ hasText: '真实节点' }).first()).toBeVisible()
  expect(downloads).toEqual([])
})

test('empty workflow disables generation', async ({ page }) => {
  const doc = document()
  doc.graph.nodes = []
  await page.addInitScript((value) => {
    localStorage.setItem('image-pipes.language', 'en')
    localStorage.setItem('image-pipes.workflow.v1', JSON.stringify(value))
  }, doc)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Code', exact: true }).click()
  await page.getByRole('button', { name: 'C++', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Export C++', exact: true })).toBeDisabled()
})
