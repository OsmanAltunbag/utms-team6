import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import Spinner from './Spinner'

interface DocumentPreviewModalProps {
  open: boolean
  onClose: () => void
  title: string
  streamUrl: string
  viewable: boolean
  contentType: string
  errorMessage: string | null
  loading?: boolean
}

export function DocumentPreviewModal({
  open,
  onClose,
  title,
  streamUrl,
  viewable,
  contentType,
  errorMessage,
  loading = false,
}: DocumentPreviewModalProps) {
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const isImage = contentType.startsWith('image/')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-900 truncate">{title}</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 text-gray-500"
            aria-label="Close preview"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto bg-gray-100 min-h-[400px] flex items-center justify-center">
          {loading ? (
            <Spinner />
          ) : !viewable ? (
            <div className="text-center p-8 max-w-md">
              <p className="text-red-700 font-medium mb-2">
                {errorMessage ?? 'Document Cannot Be Viewed – File May Be Corrupted.'}
              </p>
              <p className="text-gray-500 text-sm">
                You can request the applicant to re-upload the document.
              </p>
            </div>
          ) : isImage ? (
            <img
              src={streamUrl}
              alt={title}
              className="max-w-full max-h-[70vh] object-contain"
            />
          ) : (
            <iframe
              src={streamUrl}
              title={title}
              className="w-full h-[70vh] border-0 bg-white"
            />
          )}
        </div>
      </div>
    </div>
  )
}
