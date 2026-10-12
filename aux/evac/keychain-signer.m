// Build on macOS: clang -fobjc-arc -framework Foundation -framework Security
// This process only uses a named Keychain identity. It never exports its key.
#import <Foundation/Foundation.h>
#import <Security/Security.h>

static void fail(NSString *message) {
    fprintf(stderr, "%s\n", message.UTF8String);
    exit(1);
}

static NSString *statusText(OSStatus status) {
    return CFBridgingRelease(SecCopyErrorMessageString(status, NULL));
}

static SecKeyRef identityKey(NSString *name, SecCertificateRef *certificate) {
    SecKeychainRef keychain = NULL;
    NSString *path = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Keychains/login.keychain-db"];
    OSStatus status = SecKeychainOpen(path.fileSystemRepresentation, &keychain);
    if (status) fail(statusText(status));
    NSDictionary *query = @{
        (__bridge id)kSecClass: (__bridge id)kSecClassCertificate,
        (__bridge id)kSecReturnRef: @YES,
        (__bridge id)kSecMatchLimit: (__bridge id)kSecMatchLimitAll,
        (__bridge id)kSecMatchSearchList: @[(__bridge id)keychain]
    };
    CFTypeRef matches = NULL;
    status = SecItemCopyMatching((__bridge CFDictionaryRef)query, &matches);
    if (status) fail(statusText(status));
    SecKeyRef key = NULL;
    unsigned count = 0;
    for (id item in (__bridge NSArray *)matches) {
        SecCertificateRef cert = (__bridge SecCertificateRef)item;
        CFStringRef cn = NULL;
        if (SecCertificateCopyCommonName(cert, &cn) != errSecSuccess) continue;
        BOOL selected = [(__bridge NSString *)cn isEqualToString:name];
        CFRelease(cn);
        if (!selected) continue;
        SecIdentityRef identity = NULL;
        status = SecIdentityCreateWithCertificate(keychain, cert, &identity);
        if (status) continue;
        SecKeyRef candidate = NULL;
        status = SecIdentityCopyPrivateKey(identity, &candidate);
        CFRelease(identity);
        if (status) continue;
        if (key) CFRelease(key);
        if (*certificate) CFRelease(*certificate);
        key = candidate;
        *certificate = (SecCertificateRef)CFRetain(cert);
        count++;
    }
    CFRelease(matches);
    CFRelease(keychain);
    if (count != 1) fail([NSString stringWithFormat:@"Expected one identity for %@; found %u", name, count]);
    if (SecKeyGetBlockSize(key) != 256) fail(@"Expected the configured RSA-2048 identity");
    return key;
}

static NSString *certificatePEM(SecCertificateRef cert) {
    NSData *der = CFBridgingRelease(SecCertificateCopyData(cert));
    NSString *b64 = [der base64EncodedStringWithOptions:0];
    NSMutableString *pem = [NSMutableString stringWithString:@"-----BEGIN CERTIFICATE-----\n"];
    for (NSUInteger offset = 0; offset < b64.length; offset += 64) {
        [pem appendFormat:@"%@\n", [b64 substringWithRange:NSMakeRange(offset, MIN(64, b64.length - offset))]];
    }
    [pem appendString:@"-----END CERTIFICATE-----\n"];
    return pem;
}

static NSData *sign(SecKeyRef key, NSData *data, NSString *algorithm, NSError **error) {
    SecKeyAlgorithm alg;
    if ([algorithm isEqualToString:@"RSA_NO_PADDING"] && data.length == SecKeyGetBlockSize(key)) {
        alg = kSecKeyAlgorithmRSASignatureRaw;
    } else if ([algorithm isEqualToString:@"RSA_PKCS1_PADDING"] && data.length <= SecKeyGetBlockSize(key) - 11) {
        alg = kSecKeyAlgorithmRSASignatureDigestPKCS1v15Raw;
    } else {
        *error = [NSError errorWithDomain:@"evac-keychain-signer" code:1 userInfo:@{NSLocalizedDescriptionKey:@"Unsupported signature request"}];
        return nil;
    }
    CFErrorRef err = NULL;
    NSData *signature = CFBridgingRelease(SecKeyCreateSignature(key, alg, (__bridge CFDataRef)data, &err));
    if (err) *error = CFBridgingRelease(err);
    return signature;
}

static void signatureTest(SecKeyRef key, SecCertificateRef certificate) {
    NSMutableData *data = [NSMutableData dataWithLength:SecKeyGetBlockSize(key)];
    if (SecRandomCopyBytes(kSecRandomDefault, data.length, data.mutableBytes)) fail(@"Random generator failed");
    ((unsigned char *)data.mutableBytes)[0] = 0; // Representative below RSA modulus.
    NSError *err = nil;
    NSData *sig = sign(key, data, @"RSA_NO_PADDING", &err);
    if (!sig) fail(err.localizedDescription);
    // Legacy Keychain private keys may not support SecKeyCopyPublicKey.
    SecKeyRef pub = certificate ? SecCertificateCopyKey(certificate) : SecKeyCopyPublicKey(key);
    if (!pub) fail(@"Could not obtain public key for verification");
    CFErrorRef verifyError = NULL;
    // Recover the RSA representative explicitly. macOS raw-signature verify
    // has different behavior for public keys loaded from legacy certificates.
    NSData *recovered = CFBridgingRelease(SecKeyCreateEncryptedData(
        pub, kSecKeyAlgorithmRSAEncryptionRaw, (__bridge CFDataRef)sig, &verifyError));
    BOOL ok = [recovered isEqualToData:data];
    CFRelease(pub);
    if (!ok) fail(verifyError ? CFBridgingRelease(CFErrorCopyDescription(verifyError)) : @"RSA representative mismatch");
    if (verifyError) CFRelease(verifyError);
    puts("RSA signature verified; private key was not exported.");
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        setvbuf(stdout, NULL, _IOLBF, 0);
        BOOL noUI = NO;
        NSString *cn = nil, *mode = nil;
        for (int i = 1; i < argc; i++) {
            NSString *arg = @(argv[i]);
            if ([arg isEqualToString:@"--no-ui"]) noUI = YES;
            else if ([arg isEqualToString:@"--cn"] && i + 1 < argc) cn = @(argv[++i]);
            else if (!mode) mode = arg;
            else fail(@"Unexpected argument");
        }
        if ([mode isEqualToString:@"crypto-test"]) {
            NSDictionary *attrs = @{(__bridge id)kSecAttrKeyType:(__bridge id)kSecAttrKeyTypeRSA,
                                     (__bridge id)kSecAttrKeySizeInBits:@2048};
            CFErrorRef error = NULL;
            SecKeyRef key = SecKeyCreateRandomKey((__bridge CFDictionaryRef)attrs, &error);
            if (!key) fail(CFBridgingRelease(CFErrorCopyDescription(error)));
            signatureTest(key, NULL);
            CFRelease(key);
            return 0;
        }
        if (!cn || !mode || ![@[@"cert", @"self-test", @"serve"] containsObject:mode])
            fail(@"Usage: evac-keychain-signer --cn NAME [--no-ui] cert|self-test|serve");
        SecKeychainSetUserInteractionAllowed(!noUI);
        SecCertificateRef certificate = NULL;
        SecKeyRef key = identityKey(cn, &certificate);
        if ([mode isEqualToString:@"cert"]) {
            fputs(certificatePEM(certificate).UTF8String, stdout);
        } else if ([mode isEqualToString:@"self-test"]) {
            signatureTest(key, certificate);
        } else {
            char line[8192];
            while (fgets(line, sizeof(line), stdin)) {
                @autoreleasepool {
                    NSData *json = [@(line) dataUsingEncoding:NSUTF8StringEncoding];
                    NSError *error = nil;
                    id request = [NSJSONSerialization JSONObjectWithData:json options:0 error:&error];
                    NSDictionary *response;
                    if (![request isKindOfClass:[NSDictionary class]]) response = @{@"error":@"Invalid request"};
                    else if ([request[@"op"] isEqual:@"cert"]) response = @{@"certificate":certificatePEM(certificate)};
                    else if ([request[@"op"] isEqual:@"sign"] && [request[@"data"] isKindOfClass:[NSString class]] &&
                             [request[@"algorithm"] isKindOfClass:[NSString class]]) {
                        NSData *input = [[NSData alloc] initWithBase64EncodedString:request[@"data"] options:0];
                        NSData *sig = input ? sign(key, input, request[@"algorithm"], &error) : nil;
                        response = sig ? @{@"signature":[sig base64EncodedStringWithOptions:0]} :
                                         @{@"error":error.localizedDescription ?: @"Invalid base64"};
                    } else response = @{@"error":@"Unsupported request"};
                    NSData *output = [NSJSONSerialization dataWithJSONObject:response options:0 error:NULL];
                    fwrite(output.bytes, 1, output.length, stdout);
                    fputc('\n', stdout);
                }
            }
        }
        CFRelease(key);
        CFRelease(certificate);
    }
    return 0;
}
