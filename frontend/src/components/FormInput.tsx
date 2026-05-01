import { forwardRef, type InputHTMLAttributes } from 'react'
import type { FieldError } from 'react-hook-form'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: FieldError
}

const FormInput = forwardRef<HTMLInputElement, Props>(
  ({ label, error, id, className: _cls, ...rest }, ref) => {
    const inputId = id ?? label.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="flex flex-col gap-1">
        <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
          {label}
        </label>
        <input
          id={inputId}
          ref={ref}
          {...rest}
          className={`rounded-lg border px-3 py-2.5 text-sm outline-none transition
            focus:ring-2 focus:ring-blue-500 focus:border-blue-500
            ${error ? 'border-red-400 bg-red-50' : 'border-slate-300 bg-white hover:border-slate-400'}
            disabled:bg-slate-100 disabled:cursor-not-allowed`}
        />
        {error && <p className="text-xs text-red-600 mt-0.5">{error.message}</p>}
      </div>
    )
  },
)

FormInput.displayName = 'FormInput'
export default FormInput
