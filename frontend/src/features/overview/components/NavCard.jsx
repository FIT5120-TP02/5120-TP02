// Navigation card to go to Quiet Spaces
import styles from './NavCard.module.css'

export default function NavCard({ variant, icon, title, subtitle, onClick }) {
    return (
        <button
        className={`${styles.card} ${styles[variant]}`}
        onClick={onClick}
        >
            <span className={styles.iconWrap}>{icon}</span>
            <span className={styles.textWrap}>
                <p className={styles.title}>{title}</p>
                <p className={styles.subtitle}>{subtitle}</p>
            </span>
            <span className={styles.arrow}>→</span>
        </button>
    )
}