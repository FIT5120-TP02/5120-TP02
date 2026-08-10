import { useState } from 'react'

export default function Header(props) {
    const handleButtonClick = (buttonName) => {
        props.setActiveButton(buttonName);
    };
    const liveTime = new Date().toLocaleTimeString("en-US", { hour: '2-digit', minute: '2-digit'});
    return (
        <header>
            <div className="header-container">
                <button onClick={() => handleButtonClick('Overview')}>
                    <div className="header-icon">
                        <span>⊕</span>
                    </div>
                    <div className="header-text">
                        <h1>SenseWay</h1>
                        <p>MELBOURNE CBD</p>
                    </div>
                </button>

                <nav className="header-navigation">

                    <button className={props.activeButton === 'Plan Route' ? 'active' : ''} onClick={() => handleButtonClick('Plan Route')}><span>↗ Plan Route</span></button>
                    <button className={props.activeButton === 'Live Alerts' ? 'active' : ''} onClick={() => handleButtonClick('Live Alerts')}><span>◎ Live Alerts</span></button>
                    <button className={props.activeButton === 'Quiet Spaces' ? 'active' : ''} onClick={() => handleButtonClick('Quiet Spaces')}><span>♡ Quiet Spaces</span></button>

                </nav>
                <div className="header-live-time">
                    <span></span>
                    <span>Live {liveTime}</span>
                </div>
            </div>
        </header>
    )
}