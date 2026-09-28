import React from 'react';
import styled from 'styled-components';
export type PageId = 'home' | 'live' | 'pnr' | 'station' | 'map' | 'radar' | 'about';

interface RadioNavbarProps {
  activePage: PageId;
  onSelectPage: (page: PageId) => void;
  isRadar?: boolean;
}

export const RadioNavbar: React.FC<RadioNavbarProps> = ({ activePage, onSelectPage, isRadar }) => {
  const pages: { id: PageId; label: string; radioClass: string; index: number }[] = [
    { id: 'home', label: 'Home', radioClass: 'rd-1', index: 0 },
    { id: 'live', label: 'Live', radioClass: 'rd-2', index: 1 },
    { id: 'pnr', label: 'PNR', radioClass: 'rd-3', index: 2 },
    { id: 'station', label: 'Station', radioClass: 'rd-4', index: 3 },
    { id: 'map', label: 'Map', radioClass: 'rd-5', index: 4 },
    { id: 'radar', label: 'Control', radioClass: 'rd-6', index: 5 },
  ];

  const isAbout = activePage === 'about';

  return (
    <StyledWrapper $isRadar={isRadar} $hideIndicator={isAbout}>
      <div className="nav-container">
        <div className="wrap">
          {pages.map((item) => (
            <React.Fragment key={item.id}>
              <input
                hidden
                className={item.radioClass}
                name="rail-radio-nav"
                id={`nav-${item.id}`}
                type="radio"
                checked={activePage === item.id}
                onChange={() => onSelectPage(item.id)}
              />
              <label
                style={{ ['--index' as any]: item.index }}
                className="label"
                htmlFor={`nav-${item.id}`}
              >
                <span>{item.label}</span>
              </label>
            </React.Fragment>
          ))}
          <div className="bar" />
          <div className="slidebar" />
        </div>
      </div>
    </StyledWrapper>
  );
};

const StyledWrapper = styled.div<{ $isRadar?: boolean; $hideIndicator?: boolean }>`
  *, *::before, *::after {
    box-sizing: border-box;
  }

  .nav-container {
    --color-pure: #18191B;
    --color-primary: #FFFFFF;
    --color-secondary: #52525B;
    --muted: rgba(24, 25, 27, 0.08);
    --w-label: 106px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  @media (max-width: 1024px) and (min-width: 768px) {
    .nav-container {
      --w-label: 88px;
    }
  }

  @media (max-width: 767px) and (min-width: 641px) {
    .nav-container {
      --w-label: 78px;
    }
  }

  @media (max-width: 640px) {
    .nav-container {
      --w-label: calc((100% - 20px) / 6);
      width: 100%;
    }
  }

  /* main style from user */
  .wrap {
    --round: 9999px;
    --p-x: 14px;
    --p-y: 6px;
    display: flex;
    align-items: center;
    padding: var(--p-y) var(--p-x);
    position: relative;
    background: #FFFFFF;
    border-radius: var(--round);
    border: 1px solid rgba(24, 25, 27, 0.1);
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.16), 0 1px 4px rgba(0, 0, 0, 0.08);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    max-width: 100%;
    min-height: 54px;
    height: 54px;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    z-index: 1;
  }

  @media (max-width: 640px) {
    .wrap {
      --p-x: 8px;
      --p-y: 5px;
      min-height: 46px;
      height: 46px;
      width: 100%;
      max-width: 480px;
    }
  }

  .wrap input {
    height: 0;
    width: 0;
    position: absolute;
    overflow: hidden;
    display: none;
    visibility: hidden;
  }

  .label {
    cursor: pointer;
    outline: none;
    font-size: 0.92rem;
    letter-spacing: initial;
    font-weight: 550;
    color: var(--color-secondary);
    background: transparent;
    padding: 10px 10px;
    width: var(--w-label);
    min-width: var(--w-label);
    height: 100%;
    text-decoration: none;
    -webkit-user-select: none;
    user-select: none;
    transition: color 0.25s ease;
    outline-offset: -6px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    z-index: 2;
    -webkit-tap-highlight-color: transparent;
  }

  @media (max-width: 767px) {
    .label {
      font-size: 0.82rem;
    }
  }

  @media (max-width: 640px) {
    .label {
      font-size: 0.72rem;
      padding: 6px 2px;
      min-width: 0;
    }
  }

  .label span {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
    text-align: center;
  }

  .wrap input[class*="rd-"]:checked + label {
    color: var(--color-pure);
    font-weight: 650;
  }

  .bar {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    position: absolute;
    left: var(--p-x);
    top: 0;
    transform-origin: 0 0 0;
    height: 100%;
    width: var(--w-label);
    z-index: 0;
    opacity: ${props => props.$hideIndicator ? 0 : 1};
    visibility: ${props => props.$hideIndicator ? 'hidden' : 'visible'};
    transition: transform 0.4s cubic-bezier(0.33, 0.83, 0.99, 0.98), opacity 0.25s ease, visibility 0.25s ease;
  }
  .bar::before,
  .bar::after {
    content: "";
    position: absolute;
    height: 3px;
    width: 60%;
    background: #FF6332;
  }
  .bar::before {
    top: 2px;
    border-radius: 9999px;
  }
  .bar::after {
    bottom: 2px;
    border-radius: 9999px;
  }

  .slidebar {
    position: absolute;
    left: var(--p-x);
    top: var(--p-y);
    height: calc(100% - (var(--p-y) * 2));
    width: var(--w-label);
    border-radius: 9999px;
    background: #FFFFFF;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.04);
    transform-origin: 0 0 0;
    z-index: 0;
    opacity: ${props => props.$hideIndicator ? 0 : 1};
    visibility: ${props => props.$hideIndicator ? 'hidden' : 'visible'};
    transition: transform 0.4s cubic-bezier(0.33, 0.83, 0.99, 0.98), opacity 0.25s ease, visibility 0.25s ease;
  }

  .rd-1:checked ~ .bar,
  .rd-1:checked ~ .slidebar,
  .rd-1 + label:hover ~ .slidebar {
    transform: translateX(0) scaleX(1);
  }
  .rd-2:checked ~ .bar,
  .rd-2:checked ~ .slidebar,
  .rd-2 + label:hover ~ .slidebar {
    transform: translateX(100%) scaleX(1);
  }
  .rd-3:checked ~ .bar,
  .rd-3:checked ~ .slidebar,
  .rd-3 + label:hover ~ .slidebar {
    transform: translateX(200%) scaleX(1);
  }
  .rd-4:checked ~ .bar,
  .rd-4:checked ~ .slidebar,
  .rd-4 + label:hover ~ .slidebar {
    transform: translateX(300%) scaleX(1);
  }
  .rd-5:checked ~ .bar,
  .rd-5:checked ~ .slidebar,
  .rd-5 + label:hover ~ .slidebar {
    transform: translateX(400%) scaleX(1);
  }
  .rd-6:checked ~ .bar,
  .rd-6:checked ~ .slidebar,
  .rd-6 + label:hover ~ .slidebar {
    transform: translateX(500%) scaleX(1);
  }

  ${props => props.$hideIndicator && `
    .bar, .slidebar {
      opacity: 0 !important;
      visibility: hidden !important;
      pointer-events: none !important;
    }
  `}
`;

export default RadioNavbar;
