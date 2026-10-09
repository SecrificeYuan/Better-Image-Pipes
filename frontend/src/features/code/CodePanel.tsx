import { tr, useLocale, messageText } from '../../i18n'
import Editor from '../../i18n/LocalizedEditor'
import { Alert, Box, Button, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import { useState } from 'react'
import { useGraphStore } from '../../store/graphStore'
import { requestCodegen, requestCppCodegen } from '../../hooks/useExecutionSocket'
import { notifyError, notifySuccess } from '../../notify'

export const DEFAULT_GENERATED_CODE = '# Run codegen to export a Python script\n'

function signature() {
  const state = useGraphStore.getState()
  const graph = state.toGraphPayload()
  return JSON.stringify({
    nodes: graph.nodes.map(({ id, type, params }) => ({ id, type, params })),
    edges: graph.edges.map(({ source, source_port, target, target_port }) => ({
      source, source_port, target, target_port,
    })),
    seed: state.seed, iterations: state.iterationCount, revision: state.graphRevision,
  })
}

function download(code: string, filename: string) {
  const url = URL.createObjectURL(new Blob([code], { type: 'text/plain;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function CodePanel() {
  useLocale()
  const state = useGraphStore()
  const [language, setLanguage] = useState<'python' | 'cpp'>('python')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cpp = language === 'cpp'
  const code = cpp ? state.generatedCppCode : state.generatedCode
  const placeholder = !code.trim() || (!cpp && code.trim() === DEFAULT_GENERATED_CODE.trim())
  const stale = cpp && Boolean(code) && state.generatedCppSignature !== signature()
  const disabled = state.isExecuting || state.nodes.length === 0 || generating

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      if (cpp) {
        const requestedSignature = signature()
        const result = await requestCppCodegen()
        state.setGeneratedCppCode(result.code, requestedSignature)
        if (signature() !== requestedSignature) throw new Error('Workflow changed during export. Generate again.')
        download(result.code, result.filename)
        notifySuccess('C++ source exported')
      } else {
        state.setGeneratedCode(await requestCodegen())
        notifySuccess('Python script exported')
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Codegen failed'
      setError(message)
      notifyError(message)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ px: 2, pt: 2, pb: 1, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Typography variant="subtitle1" sx={{ fontFamily: '"Fraunces", Georgia, serif', fontWeight: 700 }}>
          {tr(cpp ? 'C++ Export' : 'Python Export')}
        </Typography>
        <ToggleButtonGroup size="small" exclusive value={language} aria-label={tr('Export language')}
          onChange={(_, next: 'python' | 'cpp' | null) => { if (next) { setLanguage(next); setError(null) } }}>
          <ToggleButton value="python">Python</ToggleButton>
          <ToggleButton value="cpp">C++</ToggleButton>
        </ToggleButtonGroup>
        <Typography sx={{ color: 'rgba(244,241,234,0.55)', fontSize: 13, lineHeight: 1.5 }}>
          {tr(cpp ? 'Generate a standalone OpenCV C++17 program from the current pipeline.' : 'Generate a standalone OpenCV script from the current pipeline.')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="outlined" disabled={disabled} onClick={() => void generate()}
            sx={{ alignSelf: 'flex-start', textTransform: 'none', fontWeight: 650,
              color: '#f0ebe3', borderColor: 'rgba(255,255,255,0.16)',
              '&:hover': { borderColor: 'rgba(125,206,160,0.45)', bgcolor: 'rgba(125,206,160,0.08)' } }}>
            {tr(generating ? 'Generating…' : cpp ? 'Export C++' : 'Export Python')}
          </Button>
          {!placeholder && <Button disabled={disabled || stale}
            onClick={() => download(code, cpp ? 'pipeline.cpp' : 'pipeline.py')}>
            {tr('Download source')}
          </Button>}
        </Box>
        {stale && <Alert severity="warning">{tr('Workflow changed. Generate C++ again before downloading.')}</Alert>}
        {error && <Alert severity="error">{messageText(error)}</Alert>}
      </Box>
      {!placeholder && <Box sx={{ flex: 1, minHeight: 0 }}>
        <Editor height="100%" language={language} value={code} theme="vs-dark"
          options={{ readOnly: true, minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }} />
      </Box>}
    </Box>
  )
}
