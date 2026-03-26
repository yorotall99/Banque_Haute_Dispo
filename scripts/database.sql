CREATE DATABASE IF NOT EXISTS isibankdb;
USE isibankdb;

-- Une seule table pour les clients
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fullname VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    account_number VARCHAR(20) UNIQUE NOT NULL, -- Très important pour une banque
    balance DECIMAL(15, 2) DEFAULT 0.00,
    account_type VARCHAR(50) DEFAULT 'Courant',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- La table des transactions pour l'historique
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT,
    montant DECIMAL(15, 2) NOT NULL,
    type_trans ENUM('DEPOT', 'RETRAIT', 'VIREMENT') NOT NULL,
    date_trans TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
);